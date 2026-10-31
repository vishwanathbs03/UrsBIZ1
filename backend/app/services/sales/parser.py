"""Sales file parser for CSV and XLSX files (Phase 3)."""

from __future__ import annotations

import io
import os
from typing import Any
import pandas as pd


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ROW_COUNT = 100_000                  # 100,000 rows


class SalesParserError(Exception):
    """Base exception for sales parsing."""


class EmptyFileError(SalesParserError):
    """Uploaded file has 0 bytes or no rows."""


class OversizedFileError(SalesParserError):
    """Uploaded file exceeds 10MB limit."""


class RowLimitExceededError(SalesParserError):
    """Uploaded file exceeds 100,000 rows."""


class UnsupportedFormatError(SalesParserError):
    """Uploaded file format is not supported."""


class MalformedFileError(SalesParserError):
    """Uploaded file content cannot be parsed."""


def validate_file_metadata(filename: str, file_bytes: bytes) -> str:
    """Validate file extension and size, returning normalized format ('csv' or 'xlsx')."""
    if len(file_bytes) == 0:
        raise EmptyFileError("Uploaded file is empty (0 bytes).")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise OversizedFileError(
            f"File size ({len(file_bytes)} bytes) exceeds the 10 MB limit."
        )

    ext = os.path.splitext(filename)[1].lower()
    if ext in [".csv", ".txt"]:
        return "csv"
    elif ext in [".xlsx", ".xls"]:
        return "xlsx"
    else:
        raise UnsupportedFormatError(
            f"Unsupported file format '{ext}'. Only CSV (.csv) and Excel (.xlsx) files are supported."
        )


def read_sales_dataframe(file_bytes: bytes, file_format: str) -> pd.DataFrame:
    """Parse file bytes into a pandas DataFrame with encoding and structure validation."""
    if file_format == "csv":
        df = None
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
        last_error = None
        for enc in encodings:
            try:
                df = pd.read_csv(
                    io.BytesIO(file_bytes),
                    encoding=enc,
                    dtype=str,  # read as string initially to prevent premature type coercion
                    on_bad_lines="skip",
                )
                break
            except Exception as e:
                last_error = e
                continue

        if df is None:
            raise MalformedFileError(f"Could not parse CSV file. Error: {last_error}")

    elif file_format == "xlsx":
        try:
            df = pd.read_excel(
                io.BytesIO(file_bytes),
                engine="openpyxl",
                dtype=str,
            )
        except Exception as e:
            raise MalformedFileError(f"Could not parse Excel file. Error: {e}")
    else:
        raise UnsupportedFormatError(f"Unknown format {file_format}")

    # Clean whitespace in column headers
    df.columns = [str(col).strip() for col in df.columns]

    if df.empty or len(df.columns) == 0:
        raise EmptyFileError("File contains no data rows or columns.")

    if len(df) > MAX_ROW_COUNT:
        raise RowLimitExceededError(
            f"File contains {len(df):,} rows, exceeding the {MAX_ROW_COUNT:,} row maximum."
        )

    return df


def generate_file_preview(
    filename: str, file_bytes: bytes
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse file and produce preview metadata with sample rows."""
    file_format = validate_file_metadata(filename, file_bytes)
    df = read_sales_dataframe(file_bytes, file_format)

    headers = list(df.columns)
    sample_df = df.head(5).fillna("")
    sample_rows = sample_df.to_dict(orient="records")

    preview_meta = {
        "filename": filename,
        "file_format": file_format,
        "file_size_bytes": len(file_bytes),
        "total_rows_estimate": len(df),
        "detected_headers": headers,
        "sample_rows": sample_rows,
    }
    return df, preview_meta
