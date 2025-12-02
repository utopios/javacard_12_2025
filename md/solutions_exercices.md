```
MF (3F00) ─────────────────────── Master File (Racine)
│
├── EF.DIR (2F00) ─────────────── Répertoire des applications PKCS#15
│   │
│   └── Contenu:
│       ┌─────────────────────────────────────────────────────────────┐
│       │ Application Template                                         │
│       │   AID: A0 00 00 00 63 50 4B 43 53 2D 31 35 (PKCS-15)       │
│       │   Label: "MyPKCS15Card"                                      │
│       │   Path: 3F00/5015                                           │
│       └─────────────────────────────────────────────────────────────┘
│
└── DF.PKCS15 (5015) ─────────── Application PKCS#15
    │
    ├── EF.ODF (5031) ─────────── Object Directory File
    │   │
    │   └── Contenu (pointeurs vers autres fichiers):
    │       ┌─────────────────────────────────────────────────────────┐
    │       │ A0 xx → Path vers PrKDF (4401)  [Private Keys]         │
    │       │ A1 xx → Path vers PuKDF (4402)  [Public Keys]          │
    │       │ A4 xx → Path vers CDF   (4403)  [Certificates]         │
    │       │ A8 xx → Path vers AODF  (4404)  [Auth Objects/PINs]    │
    │       └─────────────────────────────────────────────────────────┘
    │
    ├── EF.TokenInfo (5032) ───── Informations du token
    │   │
    │   └── Contenu:
    │       ┌─────────────────────────────────────────────────────────┐
    │       │ version: 0                                               │
    │       │ serialNumber: "12345678"                                 │
    │       │ manufacturerID: "MyCompany"                              │
    │       │ label: "MyPKCS15Card"                                    │
    │       │ tokenFlags: loginRequired, tokenInitialized              │
    │       │ lastUpdate: "20251130120000Z"                            │
    │       └─────────────────────────────────────────────────────────┘
    │
    ├── EF.PrKDF (4401) ───────── Private Key Directory File
    │   │
    │   └── Contenu (2 entrées pour 2 clés RSA):
    │       ┌─────────────────────────────────────────────────────────┐
    │       │ PrivateKey #1:                                           │
    │       │   label: "Signature Key"                                 │
    │       │   id: 01                                                 │
    │       │   usage: sign, signRecover                               │
    │       │   keyRef: 01                                             │
    │       │   path: 3F00/5015/3001                                   │
    │       │   authId: 01 (référence vers User PIN)                   │
    │       ├─────────────────────────────────────────────────────────┤
    │       │ PrivateKey #2:                                           │
    │       │   label: "Encryption Key"                                │
    │       │   id: 02                                                 │
    │       │   usage: decrypt, unwrap                                 │
    │       │   keyRef: 02                                             │
    │       │   path: 3F00/5015/3002                                   │
    │       │   authId: 01 (référence vers User PIN)                   │
    │       └─────────────────────────────────────────────────────────┘
    │
    ├── EF.PuKDF (4402) ───────── Public Key Directory File
    │   │
    │   └── Contenu (2 entrées):
    │       ┌─────────────────────────────────────────────────────────┐
    │       │ PublicKey #1:                                            │
    │       │   label: "Signature Key (Public)"                        │
    │       │   id: 01                                                 │
    │       │   usage: verify, verifyRecover                           │
    │       │   path: 3F00/5015/3003                                   │
    │       ├─────────────────────────────────────────────────────────┤
    │       │ PublicKey #2:                                            │
    │       │   label: "Encryption Key (Public)"                       │
    │       │   id: 02                                                 │
    │       │   usage: encrypt, wrap                                   │
    │       │   path: 3F00/5015/3004                                   │
    │       └─────────────────────────────────────────────────────────┘
    │
    ├── EF.CDF (4403) ─────────── Certificate Directory File
    │   │
    │   └── Contenu (2 entrées):
    │       ┌─────────────────────────────────────────────────────────┐
    │       │ Certificate #1:                                          │
    │       │   label: "Signature Certificate"                         │
    │       │   id: 01                                                 │
    │       │   authority: false (end-entity)                          │
    │       │   path: 3F00/5015/3005                                   │
    │       ├─────────────────────────────────────────────────────────┤
    │       │ Certificate #2:                                          │
    │       │   label: "Encryption Certificate"                        │
    │       │   id: 02                                                 │
    │       │   authority: false (end-entity)                          │
    │       │   path: 3F00/5015/3006                                   │
    │       └─────────────────────────────────────────────────────────┘
    │
    ├── EF.AODF (4404) ─────────── Authentication Object Directory File
    │   │
    │   └── Contenu (2 entrées pour User PIN et SO-PIN):
    │       ┌─────────────────────────────────────────────────────────┐
    │       │ PIN #1 (User PIN):                                       │
    │       │   label: "User PIN"                                      │
    │       │   authId: 01                                             │
    │       │   pinFlags: case-sensitive, initialized, needs-padding   │
    │       │   pinType: ascii-numeric (01)                            │
    │       │   minLength: 4                                           │
    │       │   storedLength: 8                                        │
    │       │   maxLength: 8                                           │
    │       │   pinReference: 01                                       │
    │       │   padChar: 0x00                                          │
    │       │   tryLimit: 3                                            │
    │       ├─────────────────────────────────────────────────────────┤
    │       │ PIN #2 (SO-PIN / Admin PIN):                             │
    │       │   label: "SO PIN"                                        │
    │       │   authId: 02                                             │
    │       │   pinFlags: case-sensitive, initialized, soPin           │
    │       │   pinType: ascii-numeric (01)                            │
    │       │   minLength: 8                                           │
    │       │   storedLength: 16                                       │
    │       │   maxLength: 16                                          │
    │       │   pinReference: 02                                       │
    │       │   padChar: 0x00                                          │
    │       │   tryLimit: 15                                           │
    │       └─────────────────────────────────────────────────────────┘
    │
    │── Fichiers de données réelles ───────────────────────────────────
    │
    ├── EF (3001) ─────────────── Private Key #1 (RSA 2048)
    │   └── [Données clé privée - NON EXPORTABLE]
    │
    ├── EF (3002) ─────────────── Private Key #2 (RSA 2048)
    │   └── [Données clé privée - NON EXPORTABLE]
    │
    ├── EF (3003) ─────────────── Public Key #1 (RSA 2048)
    │   └── [Modulus + Exponent]
    │
    ├── EF (3004) ─────────────── Public Key #2 (RSA 2048)
    │   └── [Modulus + Exponent]
    │
    ├── EF (3005) ─────────────── Certificate #1 (X.509 DER)
    │   └── [Certificat encodé DER]
    │
    └── EF (3006) ─────────────── Certificate #2 (X.509 DER)
        └── [Certificat encodé DER]
    └── EF (3007) ─────────────── PIN #2 (X.509 DER)
        └── [PIN content]
```

### Table complète des FileIDs

| FileID | Nom | Type | Description |
|--------|-----|------|-------------|
| `3F00` | MF | DF | Master File (racine) |
| `2F00` | EF.DIR | EF Transparent | Répertoire applications |
| `5015` | DF.PKCS15 | DF | Application PKCS#15 |
| `5031` | EF.ODF | EF Transparent | Object Directory |
| `5032` | EF.TokenInfo | EF Transparent | Infos token |
| `4401` | EF.PrKDF | EF Transparent | Private Key Directory |
| `4402` | EF.PuKDF | EF Transparent | Public Key Directory |
| `4403` | EF.CDF | EF Transparent | Certificate Directory |
| `4404` | EF.AODF | EF Transparent | Auth Object Directory |
| `3001` | EF.PrK1 | EF Transparent | Private Key 1 |
| `3002` | EF.PrK2 | EF Transparent | Private Key 2 |
| `3003` | EF.PuK1 | EF Transparent | Public Key 1 |
| `3004` | EF.PuK2 | EF Transparent | Public Key 2 |
| `3005` | EF.Cert1 | EF Transparent | Certificate 1 |
| `3006` | EF.Cert2 | EF Transparent | Certificate 2 |

```
MF/EF.DIR           = 3F00/2F00
MF/DF.PKCS15        = 3F00/5015
MF/DF.PKCS15/ODF    = 3F00/5015/5031
MF/DF.PKCS15/PrKDF  = 3F00/5015/4401
MF/DF.PKCS15/PrK1   = 3F00/5015/3001
...
```

**Clé privée RSA 2048 (format CRT - Chinese Remainder Theorem) :**
```
p (prime1)     = 128 bytes 
q (prime2)     = 128 bytes
dp (exp1)      = 128 bytes
dq (exp2)      = 128 bytes
qInv (coeff)   = 128 bytes
─────────────────────────────
Total          = 640 bytes par clé privée
```

**Clé publique RSA 2048 :**
```
modulus (n)    = 256 bytes (2048 bits)
exponent (e)   = 3 bytes (65537 = 0x010001)
─────────────────────────────
Total          = 259 bytes par clé publique
```

**Pour 2 paires de clés :**
```
2 × 640 bytes (privées)  = 1280 bytes
2 × 259 bytes (publiques) = 518 bytes
─────────────────────────────────────
Sous-total clés           = 1798 bytes ≈ 1.8 KB

2 certificats × 1500 bytes = 3000 bytes ≈ 3 KB
```

```
EF.DIR          ≈ 128 bytes
EF.ODF          ≈ 256 bytes
EF.TokenInfo    ≈ 128 bytes
EF.PrKDF        ≈ 256 bytes (2 entrées × ~100 bytes + overhead)
EF.PuKDF        ≈ 256 bytes
EF.CDF          ≈ 256 bytes
EF.AODF         ≈ 256 bytes (2 PINs × ~100 bytes + overhead)
─────────────────────────────
Sous-total      ≈ 1536 bytes ≈ 1.5 KB
```

```
User PIN (stockage)  ≈ 16 bytes (PIN + metadata)
SO-PIN (stockage)    ≈ 24 bytes (PIN + metadata)
PUK (optionnel)      ≈ 16 bytes
─────────────────────────────
Sous-total           ≈ 56 bytes
```