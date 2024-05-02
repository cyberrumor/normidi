#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from typing import Callable

import mido
import midi_abstraction


def normalize(source: mido.MidiFile, velocity: int) -> mido.MidiFile:
    """
    Normalize messages in source to input velocity and return source.
    """
    for track in source.tracks:
        for message in track:
            if message.type in ("note_on", "note_off"):
                message.velocity = velocity
    return source


def align(source: mido.MidiFile, precision: int = 1) -> mido.MidiFile:
    """
    Align the start and ends of notes to the quarter note intervals, aka the beat.

    Since the duration of notes are relative (at least when source.type == 1),
    shifting a note changes the absolute position of all the notes after it.
    To prevent shortening or lengthening, we have to track how far the previous
    note was shifted and accommodate the note after it.
    """
    if bin(source.ticks_per_beat).count('1') != 1:
        # ticks_per_beat aren't a power of 2.
        raise ValueError(f"Found track with {source.ticks_per_beat=} which was required to be a power of 2.")

    if bin(precision).count('1') != 1:
        # precision isn't a power of 2.
        raise ValueError(f"Precision was {precision} but was required to be a power of 2.")

    tick = source.ticks_per_beat // precision

    for track in source.tracks:
        shift = 0
        for message in track:
            if message.type not in ("note_on", "note_off"):
                continue

            if message.time + shift % tick != 0:
                original = message.time + shift
                message.time = tick * round((message.time + shift) / tick)
                shift = original - message.time

    return source


def shift_up(track: mido.MidiTrack, notes: list[int]) -> None:
    """
    Change pitch into the key by shifting notes up.
    """
    for message in track:
        if message.type not in ("note_on", "note_off"):
            continue
        # Raise the note until it's in the key.
        while message.note < 127 and message.note not in notes:
            message.note += 1
        # If we raised it too high, we will have to do the opposite.
        while message.note > 0 and message.note not in notes:
            message.note -= 1


def shift_down(track: mido.MidiTrack, notes: list[int]) -> None:
    """
    Change pitch into the key by shifting notes down.
    """
    for message in track:
        if message.type not in ("note_on", "note_off"):
            continue
        # Lower the note until it's in the key.
        while message.note > 0 and message.note not in notes:
            message.note -= 1
        # If we lowered too far, we will have to do the opposite.
        while message.note < 127 and message.note not in notes:
            message.note += 1


def shift_nearest(track: mido.MidiTrack, notes: list[int]) -> None:
    """
    Change pitch into the key by shifting notes to the nearest note in key.
    """
    # Get the absolute value of the difference between each item in
    # the list and message.note, and pick the smallest amongst them.
    for message in track:
        if message.type in ("note_on", "note_off"):
            message.note = min(notes, key=lambda x: abs(x - message.note))


def correct_pitch(
    source: mido.MidiFile,
    key: midi_abstraction.Key,
    strategy: Callable[[mido.Message], None],
) -> mido.MidiFile:
    """
    Snap pitches to notes in the given key via the strategy.
    """
    # Collect a list of midi pitches that are in the key.
    notes = []
    for n in key.list_notes():
        notes.extend(midi_abstraction.notes(n))

    for track in source.tracks:
        strategy(track, notes)

    return source
