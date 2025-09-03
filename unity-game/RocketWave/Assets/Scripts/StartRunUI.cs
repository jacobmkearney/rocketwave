using UnityEngine;
using UnityEngine.UI;

public class StartRunUI : MonoBehaviour
{
    [Header("References")]
    public GameSessionManager session;
    public RunHUD hud;

    [Header("UI Elements")]
    public InputField timeInput;
    public InputField nameInput;

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
        if (nameInput != null)
        {
            string savedName = PlayerPrefs.GetString("player_name", string.Empty);
            if (!string.IsNullOrEmpty(savedName))
            {
                nameInput.text = savedName;
            }
        }
        Debug.Log($"[StartRunUI] Awake. session set: {session != null}, hud set: {hud != null}, timeInput set: {timeInput != null}, nameInput set: {nameInput != null}");
    }

    // Hook this to the Start button's OnClick
    public void OnClickStart()
    {
        Debug.Log("[StartRunUI] OnClickStart pressed");
        // Read and persist player name
        if (nameInput != null)
        {
            string sanitized = SanitizeName(nameInput.text);
            nameInput.text = sanitized;
            PlayerPrefs.SetString("player_name", sanitized);
            PlayerPrefs.Save();
        }
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

    private static string SanitizeName(string name)
    {
        if (string.IsNullOrWhiteSpace(name)) return "Player";
        string trimmed = name.Trim();
        if (trimmed.Length > 20) trimmed = trimmed.Substring(0, 20);
        return trimmed;
    }
}


