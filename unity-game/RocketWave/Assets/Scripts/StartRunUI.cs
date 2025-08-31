using UnityEngine;
using UnityEngine.UI;

public class StartRunUI : MonoBehaviour
{
    [Header("References")]
    public GameSessionManager session;
    public RunHUD hud;

    [Header("UI Elements")]
    public InputField timeInput;

    private void Awake()
    {
        if (session == null)
        {
            session = FindObjectOfType<GameSessionManager>();
        }
        if (hud == null)
        {
            hud = FindObjectOfType<RunHUD>();
        }
        Debug.Log($"[StartRunUI] Awake. session set: {session != null}, hud set: {hud != null}, timeInput set: {timeInput != null}");
    }

    // Hook this to the Start button's OnClick
    public void OnClickStart()
    {
        Debug.Log("[StartRunUI] OnClickStart pressed");
        float seconds = session != null ? session.defaultTimeLimitSeconds : 60f;
        if (timeInput != null && !string.IsNullOrEmpty(timeInput.text))
        {
            float parsed;
            if (GameSessionManager.TryParseTimeLimit(timeInput.text.Trim(), out parsed))
            {
                seconds = parsed;
            }
            else
            {
                Debug.LogWarning($"[StartRunUI] Failed to parse time input '{timeInput.text}'. Using default {seconds}s");
            }
        }

        if (session != null)
        {
            Debug.Log($"[StartRunUI] Starting run for {seconds} seconds");
            session.StartRun(seconds);
        }
        else
        {
            Debug.LogError("[StartRunUI] No GameSessionManager found; cannot start run");
        }
        if (hud != null)
        {
            Debug.Log("[StartRunUI] Toggling HUD: OnRunStarted");
            hud.OnRunStarted();
        }
        else
        {
            Debug.LogWarning("[StartRunUI] No RunHUD reference set; HUD will not toggle");
        }
    }
}


