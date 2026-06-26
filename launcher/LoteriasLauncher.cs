using System;
using System.Diagnostics;
using System.IO;

class LoteriasLauncher
{
    static int Main()
    {
        string projectRoot = AppDomain.CurrentDomain.BaseDirectory;
        string srcDir = Path.Combine(projectRoot, "src");
        string appPath = Path.Combine(srcDir, "app.py");

        if (!File.Exists(appPath))
        {
            Console.Error.WriteLine("Nao encontrei src\\app.py ao lado do executavel.");
            Console.Error.WriteLine("Mantenha o executavel na raiz do projeto.");
            Pause();
            return 1;
        }

        string pythonCommand = FindPythonCommand();

        if (pythonCommand == null)
        {
            Console.Error.WriteLine("Nao encontrei Python instalado no PATH.");
            Console.Error.WriteLine("Instale o Python ou use o comando manual dentro de src: py app.py");
            Pause();
            return 1;
        }

        Console.WriteLine("Iniciando Gerador de Jogos de Loterias...");
        Console.WriteLine("Quando a pagina abrir, mantenha esta janela aberta enquanto usa o sistema.");
        Console.WriteLine();

        ProcessStartInfo startInfo = new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = "/c \"" + pythonCommand + " app.py\"",
            WorkingDirectory = srcDir,
            UseShellExecute = false
        };

        startInfo.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
        startInfo.EnvironmentVariables["LOTTERY_AUTO_OPEN_BROWSER"] = "1";
        startInfo.EnvironmentVariables["HOST"] = "127.0.0.1";
        startInfo.EnvironmentVariables["PORT"] = "5000";

        using (Process process = Process.Start(startInfo))
        {
            process.WaitForExit();
            return process.ExitCode;
        }
    }

    static string FindPythonCommand()
    {
        string[] candidates = { "py -3", "py", "python" };

        foreach (string candidate in candidates)
        {
            if (CommandWorks(candidate + " --version"))
            {
                return candidate;
            }
        }

        return null;
    }

    static bool CommandWorks(string command)
    {
        try
        {
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/c \"" + command + "\"",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            using (Process process = Process.Start(startInfo))
            {
                process.WaitForExit(5000);
                return process.ExitCode == 0;
            }
        }
        catch
        {
            return false;
        }
    }

    static void Pause()
    {
        Console.WriteLine();
        Console.WriteLine("Pressione qualquer tecla para fechar...");
        Console.ReadKey();
    }
}
