using UnityEngine;
using UnityEngine.UI;

public class RunHUD : MonoBehaviour
{
    [Header("References")]
    public GameSessionManager session;

    [Header("UI Elements")]
    public Text timerText;        // mm:ss
    public Text distanceText;     // distance value
    public Text avgSpeedText;     // average speed (results panel)
    public GameObject startPanel; // panel with input and start button
    public GameObject hudPanel;   // panel shown during run
    public GameObject resultsPanel; // panel shown at the end

    [Header("Display Settings")]
    public int timeMinWidth = 2;
    public string distanceUnits = "m";
    public string speedUnits = "m/s";
    public float distanceDisplayMultiplier = 1f; // world units to meters (if 1wu=1m use 1)
    public float speedDisplayMultiplier = 1f;    // multiplier for average speed display
    public int decimals = 1;

    private void Awake()
    {
        if (session == null)
        {
            session = FindObjectOfType<GameSessionManager>();
        }
        Debug.Log($"[RunHUD] Awake. Session found: {session != null}");
    }

    // Removed automatic ShowStart in OnEnable to avoid overriding runtime toggles

    public void ShowStart()
    {
        if (startPanel != null) startPanel.SetActive(true);
        if (hudPanel != null) hudPanel.SetActive(false);
        if (resultsPanel != null) resultsPanel.SetActive(false);
        Debug.Log("[RunHUD] ShowStart: startPanel ON, hudPanel OFF, resultsPanel OFF");
    }

    public void OnRunStarted()
    {
        if (startPanel != null) startPanel.SetActive(false);
        if (hudPanel != null) hudPanel.SetActive(true);
        if (resultsPanel != null) resultsPanel.SetActive(false);
        Debug.Log("[RunHUD] OnRunStarted: startPanel OFF, hudPanel ON, resultsPanel OFF");
    }

    public void OnRunFinished()
    {
        if (startPanel != null) startPanel.SetActive(false);
        if (hudPanel != null) hudPanel.SetActive(false);
        if (resultsPanel != null) resultsPanel.SetActive(true);

        if (avgSpeedText != null && session != null)
        {
            string fmt = "F" + Mathf.Clamp(decimals, 0, 3);
            float avg = session.AverageSpeed * speedDisplayMultiplier;
            avgSpeedText.text = $"Avg: {avg.ToString(fmt)} {speedUnits}";
        }
        Debug.Log("[RunHUD] OnRunFinished: startPanel OFF, hudPanel OFF, resultsPanel ON");
    }

    private void Update()
    {
        if (session == null)
        {
            return;
        }

        if (session.IsRunning)
        {
            UpdateTimerAndDistance();
        }
    }

    private void UpdateTimerAndDistance()
    {
        if (timerText != null)
        {
            FormatTime(session.TimeRemaining, out int mm, out int ss);
            timerText.text = $"{mm.ToString().PadLeft(timeMinWidth, '0')}:{ss.ToString().PadLeft(2, '0')}";
        }

        if (distanceText != null)
        {
            string fmt = "F" + Mathf.Clamp(decimals, 0, 3);
            float dist = session.TotalDistance * distanceDisplayMultiplier;
            distanceText.text = $"{dist.ToString(fmt)} {distanceUnits}";
        }
    }

    private static void FormatTime(float seconds, out int mm, out int ss)
    {
        seconds = Mathf.Max(0f, seconds);
        mm = Mathf.FloorToInt(seconds / 60f);
        ss = Mathf.FloorToInt(seconds - mm * 60);
    }
}


