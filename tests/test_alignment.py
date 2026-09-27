import unittest
from call_transcriber.alignment import parse_turns, label_word, group_words, speech_regions


class AlignmentTests(unittest.TestCase):
    def test_arrival_order_and_returning_speaker(self):
        turns = parse_turns(["3 4 speaker_0", "0 1 speaker_2", "5 6 speaker_2"])
        self.assertEqual([t["speaker"] for t in turns], ["speaker 1", "speaker 2", "speaker 1"])

    def test_overlap_and_unknown(self):
        turns = parse_turns(["0 2 a", "1 3 b"])
        self.assertEqual(label_word(.2, .8, turns), ("speaker 1", False))
        self.assertEqual(label_word(1.5, 2.5, turns), ("speaker 2", True))
        self.assertEqual(label_word(5, 6, turns), ("speaker unknown", False))

    def test_speech_union(self):
        turns = parse_turns(["0 2 a", "1 3 b", "8 9 a"])
        self.assertEqual(speech_regions(turns, 10), [[0, 3.2], [7.8, 9.2]])

    def test_turn_changes_survive_grouping(self):
        words = [dict(start=i, end=i + .5, speaker=s, text="word", overlap=False)
                 for i, s in enumerate(["speaker 1", "speaker 1", "speaker 2", "speaker 1"])]
        self.assertEqual(len(group_words(words)), 3)


if __name__ == "__main__":
    unittest.main()
