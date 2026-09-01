# Decompiling eu5.exe

The result of this work is `scripts/lib/layout.py` — a reimplementation of
the game's `ConstructTree` pass that places every advance in a tree from
the game files alone (see its docstring for the algorithm and what it was
verified against). `build_advances.py` runs it; nothing in this folder is
part of the build. What follows is how the function was found and read, so
the next patch can be re-checked.

`./setup.sh` (run from anywhere) downloads a JDK 21 and Ghidra into
`.toolbin/re/` (gitignored, ~1.2GB) and builds Ghidra's decompiler from the
C++ source it ships — no macOS binary is included in the release, and the
Makefile targets `ghidra_opt`, not `decomp_opt` (that one needs libbfd).
Nothing is installed system-wide.

Then, to decompile a function by address:

```sh
RE=$PWD/.toolbin/re
export JAVA_HOME=$RE/jdk-21.0.12.1+1/Contents/Home PATH=$JAVA_HOME/bin:$PATH
export FN_SPEC="Name:startHex:endHex,..."   # no 0x prefix
export FN_OUT=$RE/out.c
$RE/ghidra_12.1.3_PUBLIC/support/analyzeHeadless /private/tmp/eu5re eu5 \
  -process eu5.exe -noanalysis -scriptPath $RE/gs -postScript DumpFn.java
```

`-noanalysis` keeps it to seconds: the script disassembles only the range you
name and creates the function itself. The project path must not start with a
dot (Ghidra rejects it), hence `/private/tmp/eu5re`.

## Finding a function

1. `r2 -q -nn -c 'izz~<some log string>' binaries/eu5.exe` → its file offset.
2. `python3 scripts/re/xref.py <paddr>` → rip-relative references to it in
   `.text`, and the containing function's bounds read out of `.pdata`
   (the x64 exception table — exact function boundaries for free).
3. Feed those bounds to `FN_SPEC`.

`findptr.py` locates absolute 8-byte pointers (parser keyword tables map a
name string to a numeric id — `in_tree_of` is id 0x30fb); `findimm.py`
locates a 4-byte immediate and reports which functions use it.

## Section map (1.3.11)

| section | paddr | vaddr | size |
|---|---|---|---|
| .text | 0x400 | 0x140001000 | 0x5d03800 |
| .rdata | 0x5d03c00 | 0x145d05000 | 0x1882200 |
| .data | 0x7585e00 | 0x147588000 | 0xd57400 |
| .pdata | 0x82dd200 | 0x148470000 | 0x3bd600 |

Image base 0x140000000. RTTI is intact, so class names are searchable.

## Known addresses

| what | address |
|---|---|
| `ConstructTree` (advance.cpp) | 0x14429a310 – 0x14429c04c |
| `FindSlot` | 0x14429a1f0 – 0x14429a23c |
| `CountKids` | 0x14429a140 – 0x14429a15d |
| `AttachChild` | 0x14429c6a0 – 0x14429c83a |
| `LookupNode` | 0x1442981f0 – 0x144298372 |
| advance definition validation | 0x1449cb1c0 – 0x1449ccdb9 |

Advance fields seen: +0x258 parent (`requires`), +0x260 `in_tree_of`,
+0x1c4 / +0x268 / +0x548 visibility discriminators, +0x544 depth.
Tree node fields: +0x10 depth, +0x18 advance, +0x20/+0x2c child array,
+0x38 subtree width.

## Verifying against saves (superseded)

These scripts predate the decompilation and are kept for the next patch's
re-check; the layout itself now comes from `scripts/lib/layout.py`.

A melted EU5 save carries `researched_advances={ key=yes … }` per country —
~2,400 countries in a mid-game multiplayer save. Since the computed edges are
real prerequisites, every country that has an advance must also have its
ancestors, which makes the saves a **verifier**: a claimed parent P for A is
refuted the moment one country has A without P.

- `savesets.py <save.eu5> <out.json>` — extract the per-country sets.
- `chain.py` — which focus advances are ancestors of which.
- `prereq.py <advance…>` — the implied ancestor set of an advance.
- `control2.py [--gen]` — measures how well "deepest implied ancestor"
  recovers a KNOWN declared parent. It gets 193/279 on general-scope
  advances, so the saves are **not** good enough to *derive* parents:
  countries research in correlated orders, and a player who takes the
  administrative focus twice makes both ages' focus advances look like
  ancestors of each other.

Caveat: the saves in `~/Dropbox/cc/eu5stats/save` are game version 1.0.10
while `game/` is 1.3.11, so the trees need not match.

## Which tree an advance lands in

`whichtree.py <sets.json>` uses the one exact constraint available: a tree's
root is an ancestor of everything in it, so a country that researched X but
not root R proves X is not in R's tree. Run over ~2,400 countries this
eliminates candidates outright — no statistics, no thresholds. On a 1795
save it uniquely pinned the tree for 16 Discovery and 6 Absolutism orphans
and narrowed most of the rest to two or three.

**The save must come from a campaign played entirely on the patch you are
testing.** Researched advances survive a patch; the game does not re-validate
them. So a campaign begun on an older patch has lists built under the OLD
layout, and testing them against the new one produces false refutations —
it eliminates the correct tree and leaves no trace. Two cheap pre-filters:

- `metadata` containing `incompatible=yes` — the game flagging a save carried
  across patches.
- Compare the save's advance keys against `src/data/advances.json`. Between
  1.0.10 and 1.3.11, 9 advances were removed outright (`arte_della_lana`,
  `venetian_arsenal_advance`, `genoese_banking_traditions`, …). A changed
  advance list means a changed `ConstructTree` input, hence a changed layout.

A day-one save is clean but useless — nothing has been researched. What is
needed is a campaign *started* on the current patch and run a couple of
centuries.
