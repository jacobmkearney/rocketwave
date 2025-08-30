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
    }

    // Hook this to the Start button's OnClick
    public void OnClickStart()
    {
        float seconds = session != null ? session.defaultTimeLimitSeconds : 60f;
        if (timeInput != null && !string.IsNullOrEmpty(timeInput.text))
        {
            float parsed;
            if (GameSessionManager.TryParseTimeLimit(timeInput.text.Trim(), out parsed))
            {
                seconds = parsed;
            }
        }

        if (session != null)
        {
            session.StartRun(seconds);
        }
        if (hud != null)
        {
            hud.OnRunStarted();
        }
    }
}


