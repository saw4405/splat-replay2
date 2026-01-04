"""字幕フォーマット変換サービス。

SRT形式と構造化データの相互変換を担当する。
"""

from __future__ import annotations

from splat_replay.application.dto.subtitle import SubtitleBlockDTO


class SubtitleConverter:
    """字幕フォーマットの変換を担当するサービス。"""

    @staticmethod
    def from_srt(content: str) -> list[SubtitleBlockDTO]:
        """SRT形式の文字列を構造化データに変換する。

        Args:
            content: SRT形式の字幕文字列

        Returns:
            SubtitleBlockDTOのリスト

        Raises:
            ValueError: SRT形式が不正な場合
        """
        blocks: list[SubtitleBlockDTO] = []

        if not content or not content.strip():
            return blocks

        try:
            # SRT形式: 番号\n開始 --> 終了\nテキスト\n\n...
            entries = content.strip().split("\n\n")
            for entry in entries:
                lines = entry.strip().split("\n")
                if len(lines) < 3:
                    continue

                # 1行目: 番号
                try:
                    index = int(lines[0])
                except ValueError:
                    raise ValueError(
                        f"字幕番号が不正です: {lines[0]}"
                    ) from None

                # 2行目: タイムスタンプ（例: 00:00:01,000 --> 00:00:03,500）
                time_parts = lines[1].split(" --> ")
                if len(time_parts) != 2:
                    raise ValueError(
                        f"タイムスタンプ形式が不正です: {lines[1]}"
                    )

                start_time = SubtitleConverter._parse_srt_time(time_parts[0])
                end_time = SubtitleConverter._parse_srt_time(time_parts[1])

                # 3行目以降: テキスト
                text = "\n".join(lines[2:])

                blocks.append(
                    SubtitleBlockDTO(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        text=text,
                    )
                )
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"SRT形式のパースに失敗しました: {e}") from e

        return blocks

    @staticmethod
    def to_srt(blocks: list[SubtitleBlockDTO]) -> str:
        """構造化データをSRT形式の文字列に変換する。

        Args:
            blocks: SubtitleBlockDTOのリスト

        Returns:
            SRT形式の字幕文字列
        """
        srt_lines: list[str] = []

        for block in blocks:
            srt_lines.append(str(block.index))
            srt_lines.append(
                f"{SubtitleConverter._format_srt_time(block.start_time)} --> "
                f"{SubtitleConverter._format_srt_time(block.end_time)}"
            )
            srt_lines.append(block.text)
            srt_lines.append("")  # 空行

        return "\n".join(srt_lines)

    @staticmethod
    def _parse_srt_time(time_str: str) -> float:
        """SRT形式のタイムスタンプを秒に変換。

        Args:
            time_str: SRT形式のタイムスタンプ（例: "00:00:01,000"）

        Returns:
            秒数（浮動小数点）

        Raises:
            ValueError: タイムスタンプ形式が不正な場合
        """
        try:
            time_str = time_str.strip()
            parts = time_str.replace(",", ".").split(":")
            if len(parts) != 3:
                raise ValueError(f"タイムスタンプの形式が不正です: {time_str}")

            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])

            return hours * 3600 + minutes * 60 + seconds
        except (ValueError, IndexError) as e:
            raise ValueError(
                f"タイムスタンプのパースに失敗しました: {time_str}"
            ) from e

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """秒をSRT形式のタイムスタンプに変換。

        Args:
            seconds: 秒数（浮動小数点）

        Returns:
            SRT形式のタイムスタンプ（例: "00:00:01,000"）
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        milliseconds = int((secs % 1) * 1000)
        secs = int(secs)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
