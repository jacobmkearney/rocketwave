using UnityEngine;
using UnityEngine.UI;

public class ResultsUI : MonoBehaviour
{
    [Header("References")]
    public GameSessionManager session;
    public RunHUD hud;

    [Header("UI Elements")]
    public Text totalDistanceText;
    public Text averageSpeedText;

    [Header("Display Settings")]
    public string distanceUnits = "m";
    public string speedUnits = "m/s";
    public float distanceDisplayMultiplier = 1f;
    public float speedDisplayMultiplier = 1f;
    public int decimals = 1;

    private void Awake()
    {
        if (session == null) session = FindObjectOfType<GameSessionManager>();
        if (hud == null) hud = FindObjectOfType<RunHUD>();
        Debug.Log($"[ResultsUI] Awake. session set: {session != null}, hud set: {hud != null}, totalText set: {totalDistanceText != null}, avgText set: {averageSpeedText != null}");
    }

    // Hook to GameSessionManager.onRunFinished via inspector or call explicitly
    public void RefreshResults()
    {
        if (session == null)
        {
            Debug.LogError("[ResultsUI] RefreshResults called but session is null");
            return;
        }
        string fmt = "F" + Mathf.Clamp(decimals, 0, 3);

        if (totalDistanceText != null)
        {
            float dist = session.TotalDistance * distanceDisplayMultiplier;
            totalDistanceText.text = $"Total: {dist.ToString(fmt)} {distanceUnits}";
            Debug.Log($"[ResultsUI] TotalDistance updated: {dist.ToString(fmt)} {distanceUnits}");
        }
        if (averageSpeedText != null)
        {
            float avg = session.AverageSpeed * speedDisplayMultiplier;
            averageSpeedText.text = $"Avg: {avg.ToString(fmt)} {speedUnits}";
            Debug.Log($"[ResultsUI] AverageSpeed updated: {avg.ToString(fmt)} {speedUnits}");
        }
    }

    public void OnClickRetry()
    {
        Debug.Log("[ResultsUI] Retry clicked -> ShowStart");
        if (hud != null)
        {
            hud.ShowStart();
        }
        else
        {
            Debug.LogError("[ResultsUI] Retry clicked but hud is null; assign RunHUD in inspector");
        }
    }
}


