"""既存ロゴへ状態バッジを重ねる。backendのPython環境で実行する。"""

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    assets = Path(__file__).resolve().parents[1] / "backend/assets"
    destination = assets / "tray"
    destination.mkdir(exist_ok=True)
    with Image.open(assets / "icon.ico") as source:
        base = source.convert("RGBA").resize((256, 256))
    for state, color in {
        "waiting": "#16a34a",
        "recording": "#ef4444",
        "processing": "#2563eb",
        "starting": "#64748b",
        "attention": "#facc15",
    }.items():
        icon = base.copy()
        draw = ImageDraw.Draw(icon)
        draw.ellipse((120, 120, 252, 252), fill=color, outline="white", width=9)
        if state == "attention":
            draw.line((186, 148, 186, 194), fill="#111827", width=14)
            draw.ellipse((178, 207, 194, 223), fill="#111827")
        elif state == "starting":
            draw.ellipse((147, 147, 225, 225), outline="white", width=8)
            draw.line((186, 158, 186, 186, 207, 197), fill="white", width=8)
        elif state == "processing":
            draw.arc((149, 149, 223, 223), 40, 310, fill="white", width=10)
            draw.polygon(((213, 146), (229, 172), (200, 170)), fill="white")
        icon.save(
            destination / f"{state}.ico",
            sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (256, 256)],
        )


if __name__ == "__main__":
    main()
