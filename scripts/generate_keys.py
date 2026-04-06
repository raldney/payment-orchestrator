import os

import starkbank


def generate():
    print("🚀 Gerando par de chaves ECDSA para StarkBank...")
    private_key, public_key = starkbank.key.create()

    os.makedirs(".keys", exist_ok=True)

    with open(".keys/privateKey.pem", "w") as f:
        f.write(private_key)

    with open(".keys/publicKey.pem", "w") as f:
        f.write(public_key)

    print("✅ Chaves geradas com sucesso na pasta /.keys")
    print("\nPrivate Key (PEM):")
    print(private_key)
    print("\nPublic Key (PEM):")
    print(public_key)
    print("\n⚠️  COPIE a Private Key para o seu arquivo .env no campo STARK_PRIVATE_KEY")


if __name__ == "__main__":
    generate()
