using UnityEngine;
using UnityEngine.UI;

public class SpeedometerHUD : MonoBehaviour
{
    [Header("References")]
    public BackgroundScroller scroller;
    public UdpRelaxationReceiver receiver;

    [Header("UI Elements")]
    public Text speedText;
    public Slider relaxationSlider; // optional

    [Header("Display")]
    public string speedUnits = "km/h"; // display units
    public int decimals = 1;
    public float displayMultiplier = 1000f; // multiply world units to display thousands

    private void Start()
    {
        if (scroller == null) scroller = FindObjectOfType<BackgroundScroller>();
        if (receiver == null) receiver = FindObjectOfType<UdpRelaxationReceiver>();
    }

    private void Update()
    {
        if (scroller != null && speedText != null)
        {
            float speed = scroller.CurrentSpeed * displayMultiplier;
            string fmt = "F" + Mathf.Clamp(decimals, 0, 3);
            speedText.text = $"Speed: {speed.ToString(fmt)} {speedUnits}";
        }

        if (receiver != null && relaxationSlider != null)
        {
            relaxationSlider.value = Mathf.Clamp01(receiver.Relaxation01);
        }
    }
}


