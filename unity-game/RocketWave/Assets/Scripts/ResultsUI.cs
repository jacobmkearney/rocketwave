using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class ResultsUI : MonoBehaviour
{
    [Header("References")]
    public GameSessionManager session;
    public RunHUD hud;

    [Header("UI Elements")]
    public Text totalDistanceText;
    public Text averageSpeedText;
    public TextMeshProUGUI rankText; // "You placed #X of Y overall"
    public TextMeshProUGUI leaderboardText; // simple text list for Top 10

    [Header("Display Settings")]
    public string distanceUnits = "m";
    public string speedUnits = "km/h"; // match HUD
    public float distanceDisplayMultiplier = 1f; // 1 wu = 1 m
    public float speedDisplayMultiplier = 3.6f;  // m/s → km/h
    public int decimals = 1;

    [Header("Leaderboard Formatting")]
    public int nameColumnWidth = 14;   // characters
    public int speedColumnWidth = 8;   // characters for numeric avg (before units)

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
            float dist = session.TotalDistanceKilometers; // show km consistently
            totalDistanceText.text = $"Total distance: {dist.ToString(fmt)} {distanceUnits}";
            Debug.Log($"[ResultsUI] TotalDistance updated: {dist.ToString(fmt)} {distanceUnits}");
        }
        if (averageSpeedText != null)
        {
            // Read km/h directly from session to avoid double/mismatched conversions
            float avg = session.AverageSpeedKmh;
            averageSpeedText.text = $"Avg speed: {avg.ToString(fmt)} {speedUnits}";
            Debug.Log($"[ResultsUI] AverageSpeed updated: {avg.ToString(fmt)} {speedUnits}");
        }

        // Auto-save score and update rank/leaderboard
        AutoSaveAndRefreshLeaderboard();
    }

    private void AutoSaveAndRefreshLeaderboard()
    {
        if (session == null) return;
        float avg = session.AverageSpeedKmh;
        float duration = session.ElapsedTime;
        string name = PlayerPrefs.GetString("player_name", "Player");

        // Add entry and get timestamp to compute rank
        string ts = LeaderboardManager.AddEntry(name, avg, duration);
        int rank = LeaderboardManager.GetRankOf(ts);
        int total = LeaderboardManager.GetTotalEntries();

        if (rankText != null && rank > 0 && total > 0)
        {
            rankText.text = $"You placed #{rank} of {total} overall";
        }

        RefreshLeaderboardList();
    }

    private void RefreshLeaderboardList()
    {
        if (leaderboardText == null) return;
        var top = LeaderboardManager.GetTop(10);
        var sb = new System.Text.StringBuilder();

        // Bold header row
        string header = BuildLeaderboardHeader();
        sb.AppendLine(header);
        for (int i = 0; i < top.Count; i++)
        {
            var e = top[i];
            string line = FormatEntry(i + 1, e.Name, e.AvgKmh, e.DurationSeconds);
            sb.AppendLine(line);
        }
        // Monospace block so padded columns align even with proportional fonts
        leaderboardText.text = $"<mspace=0.6em>{sb.ToString()}</mspace>";
    }

    private string FormatEntry(int rank, string name, float avgKmh, float durationSeconds)
    {
        string fmt = "F" + Mathf.Clamp(decimals, 0, 3);
        string avgStr = avgKmh.ToString(fmt);
        string durStr = FormatDuration(durationSeconds);
        string rankStr = rank.ToString().PadLeft(2, ' ');
        string nameStr = TruncateAndPadRight(name, nameColumnWidth);
        string avgAligned = avgStr.PadLeft(speedColumnWidth, ' ');
        return $"{rankStr}. {nameStr}  {avgAligned} {speedUnits}  {durStr}";
    }

    private string BuildLeaderboardHeader()
    {
        string rankHdr = "#".PadLeft(2, ' ');
        string nameHdr = TruncateAndPadRight("Name", nameColumnWidth);
        string avgHdr = "Avg".PadLeft(speedColumnWidth, ' ');
        return $"<b>{rankHdr}. {nameHdr}  {avgHdr} {speedUnits}  Time</b>";
    }

    private static string TruncateAndPadRight(string value, int width)
    {
        if (string.IsNullOrEmpty(value))
        {
            return new string(' ', width);
        }
        string truncated = value.Length > width ? value.Substring(0, width) : value;
        return truncated.PadRight(width, ' ');
    }

    private static string FormatDuration(float seconds)
    {
        seconds = Mathf.Max(0f, seconds);
        int mm = Mathf.FloorToInt(seconds / 60f);
        int ss = Mathf.FloorToInt(seconds - mm * 60);
        return $"{mm.ToString().PadLeft(2, '0')}:{ss.ToString().PadLeft(2, '0')}";
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


