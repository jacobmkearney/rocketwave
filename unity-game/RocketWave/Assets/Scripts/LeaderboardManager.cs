using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

public sealed class LeaderboardEntry
{
    public string Name;
    public float AvgKmh;
    public float DurationSeconds;
    public string TimestampUtc;
}

public static class LeaderboardManager
{
    private static readonly List<LeaderboardEntry> entries = new List<LeaderboardEntry>();
    private static bool isLoaded = false;

    private static string CsvPath
    {
        get
        {
            return Path.Combine(Application.persistentDataPath, "leaderboard.csv");
        }
    }

    public static void LoadIfNeeded()
    {
        if (isLoaded) return;
        entries.Clear();
        try
        {
            string path = CsvPath;
            if (!File.Exists(path))
            {
                isLoaded = true;
                return;
            }
            string[] lines = File.ReadAllLines(path, Encoding.UTF8);
            foreach (string line in lines)
            {
                if (string.IsNullOrWhiteSpace(line)) continue;
                if (TryParseCsvLine(line, out string name, out float avgKmh, out float durationSeconds, out string timestampUtc))
                {
                    entries.Add(new LeaderboardEntry
                    {
                        Name = name,
                        AvgKmh = avgKmh,
                        DurationSeconds = durationSeconds,
                        TimestampUtc = timestampUtc
                    });
                }
            }
            SortInPlace();
            isLoaded = true;
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[LeaderboardManager] Failed to load CSV: {ex.Message}");
            entries.Clear();
            isLoaded = true;
        }
    }

    public static void Save()
    {
        LoadIfNeeded();
        try
        {
            string path = CsvPath;
            string dir = Path.GetDirectoryName(path);
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);

            string tempPath = path + ".tmp";
            using (var sw = new StreamWriter(tempPath, false, new UTF8Encoding(false)))
            {
                sw.WriteLine("name,avg_kmh,duration_s,timestamp_utc");
                for (int i = 0; i < entries.Count; i++)
                {
                    var e = entries[i];
                    sw.WriteLine(FormatCsvLine(e));
                }
            }

            if (File.Exists(path))
            {
                File.Copy(tempPath, path, true);
                File.Delete(tempPath);
            }
            else
            {
                File.Move(tempPath, path);
            }
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[LeaderboardManager] Failed to save CSV: {ex.Message}");
        }
    }

    public static string AddEntry(string name, float avgKmh, float durationSeconds)
    {
        LoadIfNeeded();
        string cleanName = SanitizeName(name);
        string timestamp = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);
        var entry = new LeaderboardEntry
        {
            Name = cleanName,
            AvgKmh = avgKmh,
            DurationSeconds = durationSeconds,
            TimestampUtc = timestamp
        };
        entries.Add(entry);
        SortInPlace();
        Save();
        return timestamp;
    }

    public static int GetTotalEntries()
    {
        LoadIfNeeded();
        return entries.Count;
    }

    public static int GetRankOf(string timestampUtc)
    {
        LoadIfNeeded();
        for (int i = 0; i < entries.Count; i++)
        {
            if (entries[i].TimestampUtc == timestampUtc)
            {
                return i + 1;
            }
        }
        return -1;
    }

    public static IReadOnlyList<LeaderboardEntry> GetTop(int count = 10)
    {
        LoadIfNeeded();
        int n = Mathf.Clamp(count, 0, entries.Count);
        if (n == entries.Count) return entries;
        return entries.GetRange(0, n);
    }

    private static void SortInPlace()
    {
        entries.Sort((a, b) =>
        {
            int byAvg = -a.AvgKmh.CompareTo(b.AvgKmh);
            if (byAvg != 0) return byAvg;
            int byDur = -a.DurationSeconds.CompareTo(b.DurationSeconds);
            if (byDur != 0) return byDur;
            return string.CompareOrdinal(a.TimestampUtc, b.TimestampUtc);
        });
    }

    private static string SanitizeName(string name)
    {
        if (string.IsNullOrWhiteSpace(name)) return "Player";
        string trimmed = name.Trim();
        if (trimmed.Length > 20) trimmed = trimmed.Substring(0, 20);
        return trimmed;
    }

    private static string FormatCsvLine(LeaderboardEntry e)
    {
        string qName = QuoteCsv(e.Name);
        string avg = e.AvgKmh.ToString("0.###", CultureInfo.InvariantCulture);
        string dur = e.DurationSeconds.ToString("0.###", CultureInfo.InvariantCulture);
        string ts = e.TimestampUtc;
        return string.Concat(qName, ",", avg, ",", dur, ",", ts);
    }

    private static bool TryParseCsvLine(string line, out string name, out float avgKmh, out float durationSeconds, out string timestampUtc)
    {
        name = string.Empty;
        avgKmh = 0f;
        durationSeconds = 0f;
        timestampUtc = string.Empty;

        List<string> parts = SplitCsv(line);
        if (parts.Count < 4)
        {
            return false;
        }
        name = UnquoteCsv(parts[0]);
        if (!float.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out avgKmh)) return false;
        if (!float.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out durationSeconds)) return false;
        timestampUtc = parts[3];
        return true;
    }

    private static List<string> SplitCsv(string line)
    {
        var list = new List<string>();
        var sb = new StringBuilder();
        bool inQuotes = false;
        for (int i = 0; i < line.Length; i++)
        {
            char c = line[i];
            if (inQuotes)
            {
                if (c == '"')
                {
                    bool isEscapedQuote = i + 1 < line.Length && line[i + 1] == '"';
                    if (isEscapedQuote)
                    {
                        sb.Append('"');
                        i++;
                    }
                    else
                    {
                        inQuotes = false;
                    }
                }
                else
                {
                    sb.Append(c);
                }
            }
            else
            {
                if (c == ',')
                {
                    list.Add(sb.ToString());
                    sb.Length = 0;
                }
                else if (c == '"')
                {
                    inQuotes = true;
                }
                else
                {
                    sb.Append(c);
                }
            }
        }
        list.Add(sb.ToString());
        return list;
    }

    private static string QuoteCsv(string value)
    {
        if (value == null) return string.Empty;
        bool needQuotes = value.Contains(",") || value.Contains("\"") || value.Contains("\n") || value.Contains("\r");
        if (!needQuotes) return value;
        string escaped = value.Replace("\"", "\"\"");
        return "\"" + escaped + "\"";
    }

    private static string UnquoteCsv(string value)
    {
        if (string.IsNullOrEmpty(value)) return string.Empty;
        if (value.Length >= 2 && value[0] == '"' && value[value.Length - 1] == '"')
        {
            string inner = value.Substring(1, value.Length - 2);
            return inner.Replace("\"\"", "\"");
        }
        return value;
    }
}


