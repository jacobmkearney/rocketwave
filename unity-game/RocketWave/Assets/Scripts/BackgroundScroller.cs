using UnityEngine;

public class BackgroundScroller : MonoBehaviour
{
    [Header("Children to Scroll (e.g., SkyA, SkyB)")]
    public Transform[] layers;

    [Header("Dimensions")]
    public float tileHeight = 10f; // world units; distance between repeated tiles vertically

    [Header("Speed")]
    public float scrollSpeed = 2f; // world units per second (downward)
    public bool useExternalSpeed = true;
    public UdpRelaxationReceiver receiver; // optional: use Relaxation01 to drive speed
    public float speedMin = 0.5f;
    public float speedMax = 8f;
    public bool invertRelaxation = false;
    [Range(0f, 1f)] public float smoothing = 0.2f; // EMA for speed changes

    private float currentSpeed;
    private float smoothedSpeed;

    // Expose the smoothed, effective scroll speed for HUD readout
    public float CurrentSpeed => smoothedSpeed;

    private void Start()
    {
        currentSpeed = scrollSpeed;
        smoothedSpeed = scrollSpeed;
        if (receiver == null)
        {
            receiver = FindObjectOfType<UdpRelaxationReceiver>();
        }
    }

    private void Update()
    {
        // Determine target speed
        if (useExternalSpeed && receiver != null)
        {
            float r = Mathf.Clamp01(receiver.Relaxation01);
            if (invertRelaxation)
            {
                r = 1f - r;
            }
            currentSpeed = Mathf.Lerp(speedMin, speedMax, r);
        }
        else
        {
            currentSpeed = scrollSpeed;
        }

        // Smooth speed to avoid jitter
        smoothedSpeed = Mathf.Lerp(smoothedSpeed, currentSpeed, 1f - Mathf.Pow(1f - smoothing, Time.deltaTime * 60f));

        // Move layers downward
        float dy = smoothedSpeed * Time.deltaTime;
        for (int i = 0; i < layers.Length; i++)
        {
            if (layers[i] == null) continue;
            layers[i].Translate(0f, -dy, 0f, Space.World);

            // If layer moved below -tileHeight/2 from root, wrap to top
            float localY = layers[i].position.y - transform.position.y;
            if (localY <= -tileHeight)
            {
                layers[i].Translate(0f, tileHeight * layers.Length, 0f, Space.World);
            }
        }
    }
}


