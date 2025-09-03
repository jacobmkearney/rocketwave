using UnityEngine;
using UnityEngine.UI;

public class SpeedometerHUD : MonoBehaviour
{
    [Header("References")]
    public BackgroundScroller scroller;
    public GameSessionManager session; // ensure we use the same scroller as session
    public UdpRelaxationReceiver receiver;

    [Header("UI Elements")]
    public Text speedText;
    public Slider relaxationSlider; // optional

    [Header("Display")]
    public string speedUnits = "km/h"; // display units
    public int decimals = 1;
    public float displayMultiplier = 3.6f; // assume 1 world unit = 1 meter; m/s → km/h

    private void Start()
    {
        if (session == null) session = FindObjectOfType<GameSessionManager>();
        if (scroller == null)
        {
            if (session != null && session != null)
            {
                scroller = session.GetComponent<GameSessionManager>() != null ? session.scroller : null;
            }
            if (scroller == null)
            {
                scroller = FindObjectOfType<BackgroundScroller>();
            }
        }
        if (receiver == null) receiver = FindObjectOfType<UdpRelaxationReceiver>();
    }

    private void Update()
    {
        if (scroller != null && speedText != null)
        {
            float speed = scroller.CurrentSpeed * 3.6f; // m/s → km/h (includes speedScale already)
            string fmt = "F" + Mathf.Clamp(decimals, 0, 3);
            speedText.text = $"{speed.ToString(fmt)} {speedUnits}";
        }

        if (receiver != null && relaxationSlider != null)
        {
            relaxationSlider.value = Mathf.Clamp01(receiver.Relaxation01);
        }
    }
}


