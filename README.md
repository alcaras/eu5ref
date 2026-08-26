# eu5ref

Reference site for **Europa Universalis V** — generated from the game's own
data files and updated each patch. Sibling of
[owreference](https://github.com/alcaras/owreference).

**Live:** https://alcaras.github.io/eu5ref/

Every fact on the site is derived from the game's script files (goods, laws,
advances, concepts, …) via the
[PyHelpersForPDXWikis](https://github.com/grotaclas/PyHelpersForPDXWikis)
EU5 parser, rendered as a static Astro site. The in-game encyclopedia's own
concept markup provides the cross-linking — everything links to everything.

See `PLAN.md` for the roadmap and `CLAUDE.md` for how the pipeline and
abstractions work.
