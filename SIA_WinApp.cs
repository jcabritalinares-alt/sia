using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Diagnostics;
using System.Threading;
using System.Windows.Forms;
using System.Drawing;

namespace SIAInventario
{
    public class Program
    {
        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string configFile = Path.Combine(baseDir, "config_red.ini");

            string modo = "servidor";
            string ip = "127.0.0.1";
            string puerto = "8000";

            if (File.Exists(configFile))
            {
                foreach (string line in File.ReadAllLines(configFile))
                {
                    string t = line.Trim();
                    if (t.StartsWith("modo")) modo = t.Split('=')[1].Trim();
                    if (t.StartsWith("ip_servidor")) ip = t.Split('=')[1].Trim();
                    if (t.StartsWith("puerto")) puerto = t.Split('=')[1].Trim();
                }
            }

            string targetIp = (modo.ToLower() == "servidor") ? "127.0.0.1" : ip;
            string targetUrl = "http://" + targetIp + ":" + puerto + "/login/";

            if (modo.ToLower() == "servidor")
            {
                if (!IsPortOpen("127.0.0.1", int.Parse(puerto)))
                {
                    StartServer(baseDir);
                    for (int i = 0; i < 20; i++)
                    {
                        if (IsPortOpen("127.0.0.1", int.Parse(puerto))) break;
                        Thread.Sleep(500);
                    }
                }
            }

            Application.Run(new DesktopAppForm(targetUrl));
        }

        private static bool IsPortOpen(string host, int port)
        {
            try {
                using (var client = new TcpClient()) {
                    var result = client.BeginConnect(host, port, null, null);
                    bool success = result.AsyncWaitHandle.WaitOne(TimeSpan.FromSeconds(1));
                    if (!success) return false;
                    client.EndConnect(result);
                    return true;
                }
            } catch { return false; }
        }

        private static void StartServer(string baseDir)
        {
            string pythonExe = Path.Combine(baseDir, "venv", "Scripts", "python.exe");
            string serverPy = Path.Combine(baseDir, "servidor.py");

            if (!File.Exists(pythonExe)) pythonExe = "python";

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = pythonExe;
            psi.Arguments = "\"" + serverPy + "\"";
            psi.WorkingDirectory = baseDir;
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;

            try { Process.Start(psi); } catch { }
        }
    }

    public class DesktopAppForm : Form
    {
        private WebBrowser webBrowser;

        public DesktopAppForm(string initialUrl)
        {
            this.Text = "SIA — Sistema de Inventario y Atención (República Bolivariana de Venezuela)";
            this.Size = new Size(1366, 820);
            this.MinimumSize = new Size(1024, 700);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = Color.FromArgb(15, 23, 42);

            webBrowser = new WebBrowser();
            webBrowser.Dock = DockStyle.Fill;
            webBrowser.ScriptErrorsSuppressed = true;
            webBrowser.IsWebBrowserContextMenuEnabled = true;

            this.Controls.Add(webBrowser);
            webBrowser.Navigate(initialUrl);
        }
    }
}
