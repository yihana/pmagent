# server/utils/doc_reader.py
from __future__ import annotations
from pathlib import Path
import mimetypes

try:
    import fitz  # PyMuPDF for PDF
except Exception:
    fitz = None

try:
    import docx  # python-docx for DOCX
except Exception:
    docx = None


class DocReadError(Exception):
    pass


def _read_text_utf8(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_bytes().decode("utf-8", errors="ignore")


def read_text_from_path(path_str: str) -> str:
    p = Path(path_str)
    if not p.exists() or not p.is_file():
        raise DocReadError(f"파일이 존재하지 않습니다: {path_str}")

    suf = p.suffix.lower()
    if suf in {".txt", ".md", ".csv", ".tsv", ".log"}:
        return _read_text_utf8(p)

    if suf == ".pdf":
        if fitz is None:
            raise DocReadError("PDF 추출을 위해 `pip install pymupdf`가 필요합니다.")
        try:
            chunks = []
            with fitz.open(p) as doc:
                for page in doc:
                    chunks.append(page.get_text("text"))
            text = "\n".join(chunks).strip()
            if not text:
                raise DocReadError("PDF에서 텍스트를 추출하지 못했습니다.")
            return text
        except Exception as e:
            raise DocReadError(f"PDF 추출 오류: {e}")

    if suf == ".docx":
        if docx is None:
            raise DocReadError("DOCX 추출을 위해 `pip install python-docx`가 필요합니다.")
        try:
            d = docx.Document(str(p))
            return "\n".join([para.text for para in d.paragraphs]).strip()
        except Exception as e:
            raise DocReadError(f"DOCX 추출 오류: {e}")

    mime, _ = mimetypes.guess_type(str(p))
    if mime and mime.startswith("text/"):
        return _read_text_utf8(p)

    raise DocReadError(f"지원하지 않는 파일 형식입니다: {p.suffix}")


def read_texts(paths: list[str], header: bool = True) -> tuple[str, list[dict]]:
    merged, metas = [], []
    for path in paths:
        if not path:
            continue
        text = read_text_from_path(path)
        merged.append((f"\n\n=== FILE: {Path(path).name} ===\n\n{text}") if header else text)
        metas.append({"path": path, "size": Path(path).stat().st_size})
    return ("\n".join(merged)).strip(), metas
