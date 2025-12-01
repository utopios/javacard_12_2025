## PKCS15 Objects

PKCS#15 définit une hiérarchie précise de fichiers :

```
MF (3F00)
│
├── EF.DIR (2F00)
│   └── Indique où trouver les applications PKCS#15
│
└── DF.PKCS15 (généralement 5015)
    │
    ├── EF.ODF (5031) ───────────── Object Directory File
    │                               "Index principal"
    │
    ├── EF.TokenInfo (5032) ─────── Informations token
    │                               "Carte d'identité de la carte"
    │
    ├── EF.AODF (typique: 4401) ─── Authentication Objects
    │                               "Définition des PINs"
    │
    ├── EF.PrKDF (typique: 4402) ── Private Key Directory
    │                               "Index des clés privées"
    │
    ├── EF.PuKDF (typique: 4403) ── Public Key Directory
    │                               "Index des clés publiques"
    │
    ├── EF.CDF (typique: 4404) ──── Certificate Directory
    │                               "Index des certificats"
    │
    └── [Fichiers de données]
        ├── Clés privées (3001, 3002, ...)
        ├── Clés publiques (3003, 3004, ...)
        └── Certificats (3005, 3006, ...)
```

### 3.3 Les fichiers Directory (xDF)

Ces fichiers ne contiennent PAS les données elles-mêmes, mais des **métadonnées** pointant vers les données.

#### Principe

```
┌────────────────────────────────────────────────────────────────┐
│                     Fichier Directory (xDF)                     │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ Entry #1                                                 │  │
│   │   label: "Ma clé de signature"                          │  │
│   │   id: 01                                                 │  │
│   │   path: 3F00/5015/3001  ─────────────► pointe vers     │  │
│   │   usage: sign                         le fichier réel   │  │
│   │   authId: 01            ─────────────► PIN requis       │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ Entry #2                                                 │  │
│   │   label: "Ma clé de chiffrement"                        │  │
│   │   id: 02                                                 │  │
│   │   path: 3F00/5015/3002                                   │  │
│   │   usage: decrypt                                         │  │
│   │   authId: 01                                             │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

#### EF.ODF - Le fichier maître

L'ODF est **l'index principal**. Il indique où trouver tous les autres fichiers directory.

```
┌────────────────────────────────────────────────────────────────┐
│                         EF.ODF (5031)                           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Contenu (encodé en ASN.1):                                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Tag A0: PrivateKeys    → Path: 3F00/5015/4401 (PrKDF)   │  │
│  │ Tag A1: PublicKeys     → Path: 3F00/5015/4402 (PuKDF)   │  │
│  │ Tag A4: Certificates   → Path: 3F00/5015/4403 (CDF)     │  │
│  │ Tag A8: AuthObjects    → Path: 3F00/5015/4404 (AODF)    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Rôle: "Voici où trouver chaque type d'objet"                  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘

Tags ODF standardisés:
┌──────┬─────────────────────┬────────────────────────────────┐
│ Tag  │ Type d'objet        │ Fichier destination            │
├──────┼─────────────────────┼────────────────────────────────┤
│ A0   │ PrivateKeys         │ → EF.PrKDF                     │
│ A1   │ PublicKeys          │ → EF.PuKDF                     │
│ A2   │ TrustedPublicKeys   │ → Clés publiques de confiance  │
│ A3   │ SecretKeys          │ → Clés symétriques             │
│ A4   │ Certificates        │ → EF.CDF                       │
│ A5   │ TrustedCertificates │ → Certificats de confiance     │
│ A6   │ UsefulCertificates  │ → Certificats utilitaires      │
│ A7   │ DataObjects         │ → EF.DODF                      │
│ A8   │ AuthObjects         │ → EF.AODF                      │
└──────┴─────────────────────┴────────────────────────────────┘
```

#### EF.TokenInfo - Informations du token

```
┌────────────────────────────────────────────────────────────────┐
│                      EF.TokenInfo (5032)                        │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Contenu:                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ version:        0 (PKCS#15 v1)                           │  │
│  │ serialNumber:   "ABC123456789"                           │  │
│  │ manufacturerID: "ACME Corp"                              │  │
│  │ label:          "Ma carte PKI"                           │  │
│  │ tokenFlags:     loginRequired, tokenInitialized          │  │
│  │ lastUpdate:     "20251130120000Z"                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Rôle: "Carte d'identité" de la carte                          │
│                                                                 │
│  tokenFlags possibles:                                          │
│  ┌────────────────────┬───────────────────────────────────┐    │
│  │ readOnly           │ Carte en lecture seule            │    │
│  │ loginRequired      │ PIN obligatoire                   │    │
│  │ prnGeneration      │ Génère des nombres aléatoires    │    │
│  │ eidCompliant       │ Compatible eID                    │    │
│  │ tokenInitialized   │ Token initialisé                  │    │
│  └────────────────────┴───────────────────────────────────┘    │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

#### EF.AODF - Définition des PINs

```
┌────────────────────────────────────────────────────────────────┐
│                         EF.AODF                                 │
│               (Authentication Object Directory File)            │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Définit les objets d'authentification (PINs, mots de passe)   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PIN Entry #1 (User PIN)                                   │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ label:        "User PIN"                                  │  │
│  │ authId:       01         ← ID unique de ce PIN           │  │
│  │                            (utilisé pour référencer)      │  │
│  │ pinFlags:                                                 │  │
│  │   - case-sensitive: true                                  │  │
│  │   - initialized: true                                     │  │
│  │   - needs-padding: true                                   │  │
│  │                                                           │  │
│  │ pinType:      01 (ascii-numeric)                          │  │
│  │               Types: 0=BCD, 1=ascii-numeric, 2=UTF8       │  │
│  │                                                           │  │
│  │ minLength:    4          ← Minimum 4 caractères          │  │
│  │ storedLength: 8          ← Stocké sur 8 bytes            │  │
│  │ maxLength:    8          ← Maximum 8 caractères          │  │
│  │                                                           │  │
│  │ pinReference: 01         ← P2 dans commande VERIFY       │  │
│  │               (00 20 00 01 ...)                           │  │
│  │                                                           │  │
│  │ padChar:      0x00       ← Caractère de padding          │  │
│  │               PIN "1234" → 31 32 33 34 00 00 00 00       │  │
│  │                                                           │  │
│  │ tryLimit:     3          ← 3 essais avant blocage        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PIN Entry #2 (SO-PIN / Admin)                             │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ label:        "SO PIN"                                    │  │
│  │ authId:       02                                          │  │
│  │ pinFlags:     soPin, case-sensitive, initialized          │  │
│  │ pinType:      01 (ascii-numeric)                          │  │
│  │ minLength:    8                                           │  │
│  │ storedLength: 16                                          │  │
│  │ maxLength:    16                                          │  │
│  │ pinReference: 02                                          │  │
│  │ tryLimit:     15         ← Plus d'essais pour l'admin    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

**Distinction User PIN vs SO-PIN :**

| Caractéristique | User PIN | SO-PIN (Security Officer) |
|-----------------|----------|---------------------------|
| Usage | Utilisateur final | Administrateur |
| Rôle | Accéder aux clés | Initialiser, débloquer |
| tryLimit | 3 (strict) | 10-15 (plus souple) |
| Peut débloquer | Non | Oui (débloque User PIN) |
| Longueur typique | 4-8 | 8-16 |

#### EF.PrKDF - Index des clés privées

```
┌────────────────────────────────────────────────────────────────┐
│                         EF.PrKDF                                │
│                 (Private Key Directory File)                    │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Chaque entrée décrit UNE clé privée:                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Private Key Entry                                         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ label:     "Signature Key"   ← Nom lisible               │  │
│  │                                                           │  │
│  │ id:        01                ← ID unique de la clé       │  │
│  │                                (lie avec certificat,      │  │
│  │                                 clé publique)             │  │
│  │                                                           │  │
│  │ usage:     sign, signRecover ← Ce que peut faire la clé  │  │
│  │                                                           │  │
│  │ keyRef:    01                ← Référence interne          │  │
│  │                                                           │  │
│  │ path:      3F00/5015/3001    ← Où est stockée la clé     │  │
│  │            (ou juste 3001)                                │  │
│  │                                                           │  │
│  │ authId:    01                ← Quel PIN pour l'utiliser? │  │
│  │            ↓                                              │  │
│  │            Référence vers AODF (User PIN authId=01)       │  │
│  │            → Il faut vérifier le User PIN avant           │  │
│  │              de pouvoir utiliser cette clé                │  │
│  │                                                           │  │
│  │ modulusLength: 2048         ← Taille RSA en bits         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Usages possibles pour les clés privées:                       │
│  ┌────────────────┬────────────────────────────────────────┐   │
│  │ sign           │ Créer une signature                    │   │
│  │ signRecover    │ Signature avec récupération message   │   │
│  │ decrypt        │ Déchiffrer des données                │   │
│  │ unwrap         │ Déballer une clé chiffrée             │   │
│  │ derive         │ Dérivation de clé (ECDH)              │   │
│  │ nonRepudiation │ Non-répudiation (signatures légales)  │   │
│  └────────────────┴────────────────────────────────────────┘   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

#### EF.PuKDF - Index des clés publiques

```
┌────────────────────────────────────────────────────────────────┐
│                         EF.PuKDF                                │
│                 (Public Key Directory File)                     │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Public Key Entry                                          │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ label:     "Signature Key (Public)"                       │  │
│  │ id:        01                ← MÊME ID que la clé privée │  │
│  │                                → Permet de les associer   │  │
│  │ usage:     verify, verifyRecover                          │  │
│  │ path:      3F00/5015/3003                                 │  │
│  │                                                           │  │
│  │ Note: Pas de authId car la clé publique est...           │  │
│  │       publique ! Pas besoin de PIN pour la lire.         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Usages possibles pour les clés publiques:                     │
│  ┌────────────────┬────────────────────────────────────────┐   │
│  │ verify         │ Vérifier une signature                 │   │
│  │ verifyRecover  │ Vérifier + récupérer message          │   │
│  │ encrypt        │ Chiffrer des données                   │   │
│  │ wrap           │ Emballer une clé                       │   │
│  └────────────────┴────────────────────────────────────────┘   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

#### EF.CDF - Index des certificats

```
┌────────────────────────────────────────────────────────────────┐
│                          EF.CDF                                 │
│                  (Certificate Directory File)                   │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Certificate Entry                                         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ label:     "Signature Certificate"                        │  │
│  │                                                           │  │
│  │ id:        01                ← MÊME ID que la clé        │  │
│  │                                → Lie certificat à clé     │  │
│  │                                                           │  │
│  │ authority: false             ← false = end-entity        │  │
│  │                                true = CA certificate      │  │
│  │                                                           │  │
│  │ path:      3F00/5015/3005    ← Où est le certificat      │  │
│  │                                                           │  │
│  │ Le certificat est stocké en format DER (binaire X.509)   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```


```
┌─────────────────────────────────────────────────────────────────┐
│                   CONVENTIONS FileID                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Plage       │  Usage                                          │
│  ─────────────┼───────────────────────────────────────────────  │
│   3F00        │  MF (Master File) - RÉSERVÉ                     │
│   2Fxx        │  EF sous MF (DIR, ATR)                          │
│   50xx        │  DF.PKCS15 et métadonnées (ODF, TokenInfo)      │
│   44xx        │  Fichiers Directory (PrKDF, PuKDF, CDF, AODF)   │
│   30xx        │  Données réelles (clés, certificats)            │
│   7Fxx        │  Autres applications (GSM, EMV...)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```


```
┌─────────────────────────────────────────────────────────────────┐
│                 TAILLES EN MÉMOIRE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CLÉS RSA (stockage complet avec CRT)                           │
│  ────────────────────────────────────────────────────────────── │
│  │ Taille    │ Clé privée  │ Clé publique  │ Paire complète │  │
│  │───────────│─────────────│───────────────│────────────────│  │
│  │ RSA 1024  │   ~320 B    │    ~140 B     │    ~460 B      │  │
│  │ RSA 2048  │   ~640 B    │    ~270 B     │    ~910 B      │  │
│  │ RSA 4096  │  ~1280 B    │    ~530 B     │   ~1810 B      │  │
│                                                                  │
│  Note: CRT = Chinese Remainder Theorem (optimisation)           │
│        Stocke p, q, dP, dQ, qInv au lieu de d complet          │
│                                                                  │
│  CLÉS EC                                                         │
│  ────────────────────────────────────────────────────────────── │
│  │ Courbe      │ Clé privée  │ Clé publique │                │  │
│  │─────────────│─────────────│──────────────│                │  │
│  │ P-256       │    ~32 B    │    ~65 B     │                │  │
│  │ P-384       │    ~48 B    │    ~97 B     │                │  │
│  │ P-521       │    ~66 B    │   ~133 B     │                │  │
│                                                                  │
│  CERTIFICATS X.509                                               │
│  ────────────────────────────────────────────────────────────── │
│  │ Type        │ Taille typique                              │  │
│  │─────────────│─────────────────────────────────────────────│  │
│  │ Simple      │  500 - 1000 B                               │  │
│  │ Standard    │ 1000 - 2000 B                               │  │
│  │ Complet     │ 2000 - 4000 B                               │  │
│                                                                  │
│  MÉTADONNÉES PKCS#15                                            │
│  ────────────────────────────────────────────────────────────── │
│  │ Fichier     │ Taille typique                              │  │
│  │─────────────│─────────────────────────────────────────────│  │
│  │ EF.DIR      │   50 - 100 B                                │  │
│  │ EF.ODF      │  100 - 200 B                                │  │
│  │ EF.TokenInfo│   50 - 150 B                                │  │
│  │ EF.AODF     │  100 - 300 B (selon nombre de PINs)        │  │
│  │ EF.PrKDF    │  100 - 200 B par clé                       │  │
│  │ EF.PuKDF    │  100 - 200 B par clé                       │  │
│  │ EF.CDF      │  100 - 200 B par certificat                │  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

```
Exemple: 2 clés RSA 2048 + 2 certificats + 2 PINs

DONNÉES CRYPTOGRAPHIQUES:
─────────────────────────
Clés privées RSA 2048:     2 × 640 B  = 1280 B
Clés publiques RSA 2048:   2 × 270 B  =  540 B
Certificats (standard):    2 × 1500 B = 3000 B
                                       ────────
                           Sous-total:  4820 B

MÉTADONNÉES PKCS#15:
────────────────────
EF.DIR:                              100 B
EF.ODF:                              150 B
EF.TokenInfo:                        100 B
EF.AODF (2 PINs):                    250 B
EF.PrKDF (2 entrées):                300 B
EF.PuKDF (2 entrées):                300 B
EF.CDF (2 entrées):                  300 B
                                   ────────
                        Sous-total: 1500 B

OVERHEAD SYSTÈME:
─────────────────
Headers fichiers (14 fichiers × 20 B):  280 B
Marge de sécurité (10%):                660 B
                                       ────────
                           Sous-total:  940 B

═══════════════════════════════════════════════
TOTAL ESTIMÉ:                          ~7260 B
                                       ≈ 7.1 KB
═══════════════════════════════════════════════

Pour une carte 32 KB EEPROM: OK ✓
Pour une carte 16 KB EEPROM: OK ✓
Pour une carte 8 KB EEPROM:  Limite ⚠️
```