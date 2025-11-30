#!/usr/bin/env python3
"""Тест функций padding для нарезки видео."""

from utils import (
    apply_padding_to_timecodes,
    check_overlapping_segments,
    format_duration
)

def test_basic_padding():
    """Тест базового применения padding."""
    print("Test 1: Basic padding")
    timecodes = [(100, 200), (300, 400)]
    padded = apply_padding_to_timecodes(timecodes, 2, 2)
    
    print(f"Original: {timecodes}")
    print(f"Padded:   {padded}")
    assert padded == [(98, 202), (298, 402)], "Basic padding failed"
    print("✅ Passed\n")


def test_boundary_check():
    """Тест проверки границ (не уходит в отрицательные значения)."""
    print("Test 2: Boundary check (negative)")
    timecodes = [(1, 10)]
    padded = apply_padding_to_timecodes(timecodes, 2, 2)
    
    print(f"Original: {timecodes}")
    print(f"Padded:   {padded}")
    assert padded[0][0] == 0, "Should not go below 0"
    print("✅ Passed\n")


def test_video_duration_limit():
    """Тест проверки границ (не превышает длительность видео)."""
    print("Test 3: Video duration limit")
    timecodes = [(100, 195)]
    video_duration = 200
    padded = apply_padding_to_timecodes(timecodes, 2, 2, video_duration)
    
    print(f"Original: {timecodes}")
    print(f"Padded:   {padded}")
    print(f"Video duration: {video_duration}")
    assert padded[0][1] == 197, f"Should not exceed video duration, got {padded[0][1]}"
    print("✅ Passed\n")


def test_overlapping_detection():
    """Тест обнаружения пересечений."""
    print("Test 4: Overlapping detection")
    
    # Без пересечений
    timecodes1 = [(0, 10), (20, 30), (40, 50)]
    overlaps1 = check_overlapping_segments(timecodes1)
    print(f"Timecodes (no overlap): {timecodes1}")
    print(f"Overlaps: {overlaps1}")
    assert len(overlaps1) == 0, "Should not detect overlaps"
    print("✅ No overlaps detected\n")
    
    # С пересечениями
    timecodes2 = [(0, 15), (10, 25), (30, 40)]
    overlaps2 = check_overlapping_segments(timecodes2)
    print(f"Timecodes (with overlap): {timecodes2}")
    print(f"Overlaps: {overlaps2}")
    assert len(overlaps2) == 1, "Should detect 1 overlap"
    assert overlaps2[0] == (0, 1), "Should detect overlap between segments 0 and 1"
    print("✅ Overlap detected correctly\n")


def test_real_world_example():
    """Тест реального примера из требований."""
    print("Test 5: Real-world example")
    # Пример: 4:40:00-4:51:36 → 4:39:58-4:51:38
    # 4:40:00 = 16800 секунд
    # 4:51:36 = 17496 секунд
    
    timecodes = [(16800, 17496)]
    padded = apply_padding_to_timecodes(timecodes, 2, 2)
    
    print(f"Original: {format_duration(timecodes[0][0])}-{format_duration(timecodes[0][1])}")
    print(f"Padded:   {format_duration(padded[0][0])}-{format_duration(padded[0][1])}")
    
    assert padded[0][0] == 16798, f"Start should be 16798, got {padded[0][0]}"
    assert padded[0][1] == 17498, f"End should be 17498, got {padded[0][1]}"
    print("✅ Passed\n")


if __name__ == "__main__":
    print("=" * 50)
    print("Testing Padding Functions")
    print("=" * 50 + "\n")
    
    try:
        test_basic_padding()
        test_boundary_check()
        test_video_duration_limit()
        test_overlapping_detection()
        test_real_world_example()
        
        print("=" * 50)
        print("✅ All tests passed!")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
