import os
from faster_whisper import WhisperModel

INPUT_DIR = "/app/input"
OUTPUT_DIR = "/app/output"

model = WhisperModel("medium", compute_type="int8")

for filename in os.listdir(INPUT_DIR):
    if filename.lower().endswith((".mp3", ".wav")):
        input_path = os.path.join(INPUT_DIR, filename)
        output_filename = os.path.splitext(filename)[0] + ".txt"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        print(f"🎧 Transcription de : {filename}")
        segments, _ = model.transcribe(input_path, beam_size=5)

        with open(output_path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(seg.text + "\n")

        print(f"✅ Fichier généré : {output_filename}")