"""rip-relative xrefs into .text for a given .rdata paddr, + containing function from .pdata."""
import numpy as np, struct, sys
PATH='binaries/eu5.exe'
IMAGE_BASE=0x140000000
TEXT_PADDR, TEXT_SIZE, TEXT_VADDR = 0x400, 0x5d03800, 0x140001000
RDATA_PADDR, RDATA_VADDR = 0x05d03c00, 0x145d05000
PDATA_PADDR, PDATA_SIZE = 0x082dd200, 0x3bd600
with open(PATH,'rb') as f:
    f.seek(TEXT_PADDR); text=f.read(TEXT_SIZE)
    f.seek(PDATA_PADDR); pdata=f.read(PDATA_SIZE)
def xrefs(target):
    hits=[]; n=len(text)
    for off in range(4):
        cnt=(n-off)//4
        arr=np.frombuffer(text, dtype='<u4', count=cnt, offset=off)
        idx=np.arange(cnt, dtype=np.int64)*4+off
        need=((target-TEXT_VADDR-idx-4)&0xFFFFFFFF).astype(np.uint32)
        for j in np.nonzero(arr==need)[0]: hits.append(int(idx[j]))
    return sorted(hits)
def func_of(va):
    rva=va-IMAGE_BASE
    for i in range(len(pdata)//12):
        b,e,u=struct.unpack_from('<III', pdata, i*12)
        if b<=rva<e: return (IMAGE_BASE+b, IMAGE_BASE+e)
for p in sys.argv[1:]:
    paddr=int(p,16); va=RDATA_VADDR+(paddr-RDATA_PADDR)
    print(f'== {paddr:#x} -> vaddr {va:#x}')
    for off in xrefs(va):
        ia=TEXT_VADDR+off; fn=func_of(ia)
        print(f'   ref {ia:#x}  fn {fn[0]:#x}:{fn[1]:#x} size {fn[1]-fn[0]}' if fn else f'   ref {ia:#x} (no pdata)')
