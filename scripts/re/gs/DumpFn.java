// Decompile functions by address using .pdata-derived bounds.
// FN_SPEC="name:startHex:endHex,..."  FN_OUT=<file>
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class DumpFn extends GhidraScript {
    public void run() throws Exception {
        String spec = System.getenv("FN_SPEC");
        String out  = System.getenv("FN_OUT");
        PrintWriter w = new PrintWriter(new FileWriter(out));
        DecompInterface dec = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        opts.setMaxPayloadMBytes(512);
        dec.setOptions(opts);
        dec.toggleCCode(true);
        if (!dec.openProgram(currentProgram)) println("openProgram FAILED: " + dec.getLastMessage());
        for (String part : spec.split(",")) {
            String[] f = part.split(":");
            String name = f[0];
            Address start = toAddr(Long.parseUnsignedLong(f[1], 16));
            Address end   = toAddr(Long.parseUnsignedLong(f[2], 16) - 1);
            AddressSet body = new AddressSet(start, end);
            new DisassembleCommand(body, body, true).applyTo(currentProgram, monitor);
            Function fn = getFunctionAt(start);
            if (fn != null) removeFunction(fn);
            fn = currentProgram.getFunctionManager()
                    .createFunction(name, start, body, SourceType.USER_DEFINED);
            DecompileResults r = dec.decompileFunction(fn, 900, monitor);
            w.println("//////// " + name + " @ " + start + " ////////");
            w.println(r != null && r.decompileCompleted()
                ? r.getDecompiledFunction().getC()
                : "// FAILED: " + (r == null ? "null" : r.getErrorMessage()));
            w.flush();
            println("done " + name);
        }
        w.close();
    }
}
