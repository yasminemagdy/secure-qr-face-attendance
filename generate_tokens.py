"""Fill the 'QR Token' column of the roster with a SHA-256 hash of ID + SessionID + passcode.

Usage: python3 generate_tokens.py data/students.xlsx YOUR_PRIVATE_PASSCODE
"""
import sys
import hashlib
import pandas as pd

if len(sys.argv) != 3:
    sys.exit("Usage: python3 generate_tokens.py <roster.xlsx> <passcode>")

path, passcode = sys.argv[1], sys.argv[2]
df = pd.read_excel(path, engine="openpyxl")

for col in ("ID", "SessionID"):
    if col not in df.columns:
        sys.exit(f"Missing required column: {col}")

df["QR Token"] = [
    hashlib.sha256(f"{row.ID}{row.SessionID}{passcode}".encode()).hexdigest()
    for row in df.itertuples()
]
df.to_excel(path, index=False)
print(f"Wrote {len(df)} tokens to {path}")
