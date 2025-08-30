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
    }

    // Hook to GameSessionManager.onRunFinished via inspector or call explicitly
    public void RefreshResults()
    {
        if (session == null) return;
        string fmt = "F" + Mathf.Clamp(decimals, 0, 3);

        if (totalDistanceText != null)
        {
            float dist = session.TotalDistance * distanceDisplayMultiplier;
            totalDistanceText.text = $"Total: {dist.ToString(fmt)} {distanceUnits}";
        }
        if (averageSpeedText != null)
        {
            float avg = session.AverageSpeed * speedDisplayMultiplier;
            averageSpeedText.text = $"Avg: {avg.ToString(fmt)} {speedUnits}";
        }
    }

    public void OnClickRetry()
    {
        if (hud != null)
        {
            hud.ShowStart();
        }
    }
}


