import struct, sys
PATH='binaries/eu5.exe'
SECS=[('.text',0x400,0x5d03800,0x140001000),('.rdata',0x05d03c00,0x1882200,0x145d05000),
      ('.data',0x07585e00,0xd57400,0x147588000)]
targets=[int(a,16) for a in sys.argv[1:]]
with open(PATH,'rb') as f: blob=f.read()
for name,paddr,size,vaddr in SECS:
    buf=blob[paddr:paddr+size]
    for t in targets:
        pat=struct.pack('<Q', t)
        start=0
        while True:
            i=buf.find(pat, start)
            if i<0: break
            print(f'{name}: qword {t:#x} at paddr {paddr+i:#x} vaddr {vaddr+i:#x}')
            ctx=buf[max(0,i-32):i+48]
            print('   ctx:', ' '.join(f'{b:02x}' for b in ctx))
            start=i+1
