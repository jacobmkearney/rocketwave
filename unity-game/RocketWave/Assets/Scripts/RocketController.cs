using UnityEngine;

public class RocketController : MonoBehaviour
{
    [Header("References")]
    public UdpRelaxationReceiver receiver;

    [Header("Movement")]
    public float vMin = 0.5f;
    public float vMax = 5.0f;

    [Header("Crash Rule")]
    [Range(0f, 1f)] public float crashFloor = 0.2f;
    public float crashHoldSeconds = 2f;

    private float belowTimer = 0f;
    private Vector3 startPosition;

    private void Start()
    {
        startPosition = transform.position;
        if (receiver == null)
        {
            receiver = FindObjectOfType<UdpRelaxationReceiver>();
        }
    }

    private void Update()
    {
        float r = receiver != null ? receiver.Relaxation01 : 0f;
        float vy = Mathf.Lerp(vMin, vMax, r);
        transform.Translate(Vector3.up * vy * Time.deltaTime, Space.World);

        if (r < crashFloor)
        {
            belowTimer += Time.deltaTime;
        }
        else
        {
            belowTimer = 0f;
        }

        if (belowTimer >= crashHoldSeconds)
        {
            // Simple reset: snap to start Y and clear timer (placeholder for animation)
            transform.position = new Vector3(transform.position.x, startPosition.y, transform.position.z);
            belowTimer = 0f;
        }
    }
}


