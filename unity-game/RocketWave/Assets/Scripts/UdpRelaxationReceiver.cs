using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

[System.Serializable]
public class RelaxationPacket
{
    public double t;
    public float ri;
    public float ri_ema;
    public float ri_scaled;
    public bool ok;
}

public class UdpRelaxationReceiver : MonoBehaviour
{
    [Header("UDP Settings")]
    public int port = 5005;

    [Header("Runtime State")] 
    [Range(0f, 1f)] public volatile float Relaxation01 = 0f;

    private UdpClient udpClient;
    private Thread listenerThread;
    private volatile bool isRunning;

    private void Start()
    {
        try
        {
            udpClient = new UdpClient(port);
            isRunning = true;
            listenerThread = new Thread(ListenLoop) { IsBackground = true };
            listenerThread.Start();
            Debug.Log($"[UdpRelaxationReceiver] Listening on UDP :{port}");
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"[UdpRelaxationReceiver] Failed to bind UDP port {port}: {ex.Message}");
        }
    }

    private void ListenLoop()
    {
        IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, port);
        while (isRunning)
        {
            try
            {
                byte[] data = udpClient.Receive(ref remoteEndPoint);
                string json = Encoding.UTF8.GetString(data);
                var pkt = JsonUtility.FromJson<RelaxationPacket>(json);
                if (pkt != null && pkt.ok)
                {
                    float value = Mathf.Clamp01(pkt.ri_scaled);
                    Relaxation01 = value;
                }
            }
            catch (SocketException)
            {
                // Expected when closing UDP or if no data; ignore.
                if (!isRunning) break;
            }
            catch
            {
                // Ignore malformed packets.
            }
        }
    }

    private void OnDestroy()
    {
        isRunning = false;
        try { udpClient?.Close(); } catch { }
        if (listenerThread != null && listenerThread.IsAlive)
        {
            try { listenerThread.Join(100); } catch { }
        }
    }
}


