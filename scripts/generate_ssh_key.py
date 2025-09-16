#!/usr/bin/env python3
"""
Generate an ed25519 SSH keypair and print the public key in OpenSSH format.
If key exists at ~/.ssh/id_ed25519_langchain_rag, print that public key instead.
"""
import argparse
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
except Exception:
    print(
        "Missing 'cryptography' package. Install it with: python -m pip install cryptography",
        file=sys.stderr,
    )
    raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out", "-o", help="Output base path for key (default: ~/.ssh/id_ed25519_langchain_rag)"
    )
    p.add_argument(
        "--comment",
        "-c",
        default=None,
        help="Comment to append to public key (default: git user.email or user@host)",
    )
    args = p.parse_args()

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    key_base = Path(args.out) if args.out else ssh_dir / "id_ed25519_langchain_rag"
    priv_path = key_base
    pub_path = (
        key_base.with_suffix(key_base.suffix + ".pub")
        if key_base.suffix
        else key_base.with_suffix(".pub")
    )

    # If public exists, print and exit
    if pub_path.exists():
        print("Public key already exists at:", pub_path)
        print(pub_path.read_text())
        return

    # Generate new ed25519 key
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Private key in OpenSSH (PEM-like) format
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Public key in OpenSSH "ssh-ed25519 AAAA..." format
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )

    comment = args.comment
    if not comment:
        # try to get from git config
        try:
            import subprocess

            out = subprocess.check_output(["git", "config", "--get", "user.email"]).decode().strip()
            if out:
                comment = out
        except Exception:
            pass
    if not comment:
        comment = f"{Path.home().name}@{Path.home().anchor.replace(':','').rstrip('\\')}"

    # Write private and public
    priv_path.write_bytes(priv_bytes)
    # Set restrictive perms where possible
    try:
        priv_path.chmod(0o600)
    except Exception:
        pass

    pub_text = pub_bytes.decode() + " " + comment + "\n"
    pub_path.write_text(pub_text)

    print("Wrote private key to:", priv_path)
    print("Wrote public key to:", pub_path)
    print("\nPublic key:\n")
    print(pub_text)


if __name__ == "__main__":
    main()
