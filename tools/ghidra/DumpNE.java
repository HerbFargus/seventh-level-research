// Dump every function's decompiled C to <out>.c plus strings with their xrefs.
//@category SeventhLevel
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class DumpNE extends GhidraScript {
    @Override
    public void run() throws Exception {
        String out = getScriptArgs()[0];
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new FileWriter(out + ".c"))) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                w.println("// ==== " + f.getName() + " @ " + f.getEntryPoint());
                if (r.decompileCompleted()) w.println(r.getDecompiledFunction().getC());
                else w.println("// decompile failed: " + r.getErrorMessage());
            }
        }
        try (PrintWriter w = new PrintWriter(new FileWriter(out + ".strings.txt"))) {
            for (Data d : currentProgram.getListing().getDefinedData(true)) { if (!d.hasStringValue()) continue;
                StringBuilder refs = new StringBuilder();
                for (Reference ref : getReferencesTo(d.getAddress())) {
                    Function f = getFunctionContaining(ref.getFromAddress());
                    refs.append(" ").append(f == null ? ref.getFromAddress().toString() : f.getName());
                }
                w.println(d.getAddress() + "\t" + d.getDefaultValueRepresentation() + "\t<-" + refs);
            }
        }
    }
}
