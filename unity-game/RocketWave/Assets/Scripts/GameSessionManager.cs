using UnityEngine;
using UnityEngine.Events;

public class GameSessionManager : MonoBehaviour
{
    [Header("References")]
    public BackgroundScroller scroller;
    public RocketController rocket; // optional: to freeze or reset on finish

    [Header("Config")]
    [Min(1f)] public float defaultTimeLimitSeconds = 60f;

    [Header("Runtime (read-only)")]
    [SerializeField] private bool isRunning = false;
    [SerializeField] private float timeRemaining = 0f;
    [SerializeField] private float elapsedTime = 0f;
    [SerializeField] private float totalDistance = 0f;

    [Header("Units")] 
    [Tooltip("Meters per world unit. If 1 wu = 1 meter, leave as 1.0")] 
    public float metersPerWorldUnit = 1f;

    [Header("Events")]
    public UnityEvent onRunStarted;
    public UnityEvent onRunFinished;

    public bool IsRunning => isRunning;
    public float TimeRemaining => timeRemaining;
    public float ElapsedTime => elapsedTime;
    public float TotalDistance => totalDistance;
    // Total distance in meters/kilometers
    public float TotalDistanceMeters => totalDistance * metersPerWorldUnit;
    public float TotalDistanceKilometers => TotalDistanceMeters / 1000f;

    // Average speed in m/s and km/h using metersPerWorldUnit
    public float AverageSpeed => elapsedTime > 0.001f ? (TotalDistanceMeters / elapsedTime) : 0f;
    public float AverageSpeedKmh => elapsedTime > 0.001f ? (TotalDistanceMeters / elapsedTime) * 3.6f : 0f;

    private void Awake()
    {
        if (scroller == null)
        {
            scroller = FindObjectOfType<BackgroundScroller>();
        }
        if (rocket == null)
        {
            rocket = FindObjectOfType<RocketController>();
        }
    }

    private void Update()
    {
        if (!isRunning || scroller == null)
        {
            return;
        }

        float dt = Time.deltaTime;
        timeRemaining -= dt;
        elapsedTime += dt;
        totalDistance += scroller.CurrentSpeed * dt; // includes speedScale already

        if (timeRemaining <= 0f)
        {
            EndRun();
        }
    }

    public void StartRun(float seconds)
    {
        float limit = Mathf.Max(1f, seconds);
        timeRemaining = limit;
        elapsedTime = 0f;
        totalDistance = 0f;
        isRunning = true;
        Debug.Log($"[GameSessionManager] Run started for {limit} seconds");
        onRunStarted?.Invoke();
    }

    public void StartDefaultRun()
    {
        StartRun(defaultTimeLimitSeconds);
    }

    public void EndRun()
    {
        if (!isRunning)
        {
            return;
        }
        isRunning = false;
        timeRemaining = 0f;
        Debug.Log($"[GameSessionManager] Run finished. Elapsed={elapsedTime:F2}s, Distance={totalDistance:F2} wu, Avg={AverageSpeedKmh:F2} km/h");
        onRunFinished?.Invoke();
    }

    public static bool TryParseTimeLimit(string text, out float seconds)
    {
        seconds = 0f;
        if (string.IsNullOrEmpty(text))
        {
            return false;
        }

        // Accept MM:SS or SS
        if (text.Contains(":"))
        {
            string[] parts = text.Split(':');
            if (parts.Length != 2)
            {
                return false;
            }
            int mm, ss;
            if (!int.TryParse(parts[0], out mm)) return false;
            if (!int.TryParse(parts[1], out ss)) return false;
            mm = Mathf.Max(0, mm);
            ss = Mathf.Clamp(ss, 0, 59);
            seconds = mm * 60 + ss;
            return true;
        }

        float sec;
        if (float.TryParse(text, out sec))
        {
            seconds = Mathf.Max(0f, sec);
            return true;
        }

        return false;
    }
}


