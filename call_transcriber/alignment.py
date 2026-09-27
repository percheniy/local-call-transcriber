"""Speaker and word timeline alignment."""
def parse_turns(lines):
    turns = []
    for line in lines:
        start, end, speaker = line.split()
        if float(end) > float(start):
            turns.append(dict(start=float(start), end=float(end), raw_speaker=speaker))
    turns.sort(key=lambda t: (t["start"], t["end"]))
    names = {}
    for turn in turns:
        raw = turn.pop("raw_speaker")
        names.setdefault(raw, f"speaker {len(names) + 1}")
        turn["speaker"] = names[raw]
    return turns


def speech_regions(turns, duration):
    regions = []
    for turn in turns:
        start, end = max(0, turn["start"] - .2), min(duration, turn["end"] + .2)
        if regions and start <= regions[-1][1] + .6:
            regions[-1][1] = max(regions[-1][1], end)
        else:
            regions.append([start, end])
    return regions


def label_word(start, end, turns):
    scores = {}
    for turn in turns:
        overlap = max(0, min(end, turn["end"]) - max(start, turn["start"]))
        scores[turn["speaker"]] = scores.get(turn["speaker"], 0) + overlap
    active = [name for name, score in scores.items() if score > 0]
    if active:
        return max(active, key=lambda name: scores[name]), len(active) > 1
    midpoint = (start + end) / 2
    nearest = min(turns, key=lambda t: max(t["start"] - midpoint, midpoint - t["end"], 0))
    distance = max(nearest["start"] - midpoint, midpoint - nearest["end"], 0)
    return (nearest["speaker"] if distance <= .5 else "speaker unknown"), False


def group_words(words):
    segments = []
    for word in words:
        if (segments and segments[-1]["speaker"] == word["speaker"]
                and word["start"] - segments[-1]["end"] < 1.2):
            segment = segments[-1]
            segment["end"] = word["end"]
            segment["text"] += " " + word["text"]
            segment["overlap"] |= word["overlap"]
        else:
            segments.append(dict(word))
    return segments


def timestamp(seconds):
    total = round(seconds)
    return f"{total // 3600:02}:{total // 60 % 60:02}:{total % 60:02}"


