# Decompiling eu5.exe

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
