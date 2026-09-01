import struct, sys
PATH='binaries/eu5.exe'
TEXT_PADDR, TEXT_SIZE, TEXT_VADDR = 0x400, 0x5d03800, 0x140001000
PDATA_PADDR, PDATA_SIZE = 0x082dd200, 0x3bd600
IMAGE_BASE=0x140000000
with open(PATH,'rb') as f:
    f.seek(TEXT_PADDR); text=f.read(TEXT_SIZE)
    f.seek(PDATA_PADDR); pdata=f.read(PDATA_SIZE)
def func_of(va):
    rva=va-IMAGE_BASE
    for i in range(len(pdata)//12):
        b,e,u=struct.unpack_from('<III', pdata, i*12)
        if b<=rva<e: return (IMAGE_BASE+b, IMAGE_BASE+e)
val=int(sys.argv[1],16)
pat=struct.pack('<I', val)
start=0; seen={}
while True:
    i=text.find(pat, start)
    if i<0: break
    va=TEXT_VADDR+i
    fn=func_of(va)
    if fn: seen.setdefault(fn, []).append(va)
    start=i+1
for fn, refs in sorted(seen.items(), key=lambda kv:-len(kv[1]))[:10]:
    print(f'fn {fn[0]:#x}:{fn[1]:#x} size {fn[1]-fn[0]}  refs={len(refs)} {[hex(r) for r in refs[:4]]}')
