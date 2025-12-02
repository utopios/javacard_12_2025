# Projet Final : E-Wallet Sécurisé

## Énoncé complet

Implémenter un portefeuille électronique (E-Wallet) sur Java Card avec :
- Balance initiale : 100 unités
- Crédit/Débit avec transactions atomiques
- User PIN (3 essais)
- Historique des 10 dernières transactions

---

## Solution : Applet E-Wallet complète

```java
package com.formation.ewallet;

import javacard.framework.*;
import javacard.security.*;

/**
 * E-Wallet Applet - Portefeuille électronique sécurisé
 *
 * AID recommandé : F0 00 00 00 02 00 01
 *
 * Instructions APDU:
 * - 0x20 : VERIFY_PIN
 * - 0x30 : CREDIT
 * - 0x40 : DEBIT
 * - 0x50 : GET_BALANCE
 * - 0x60 : GET_HISTORY
 * - 0x70 : CHANGE_PIN
 */
public class EWalletApplet extends Applet {

    // ═══════════════════════════════════════════════════════════
    // CONSTANTES
    // ═══════════════════════════════════════════════════════════

    // Instructions
    private static final byte INS_VERIFY_PIN   = (byte) 0x20;
    private static final byte INS_CREDIT       = (byte) 0x30;
    private static final byte INS_DEBIT        = (byte) 0x40;
    private static final byte INS_GET_BALANCE  = (byte) 0x50;
    private static final byte INS_GET_HISTORY  = (byte) 0x60;
    private static final byte INS_CHANGE_PIN   = (byte) 0x70;

    // Limites PIN
    private static final byte PIN_TRY_LIMIT    = (byte) 3;
    private static final byte PIN_MIN_LENGTH   = (byte) 4;
    private static final byte PIN_MAX_LENGTH   = (byte) 8;

    // Limites balance
    private static final short INITIAL_BALANCE = (short) 100;
    private static final short MAX_BALANCE     = (short) 10000;
    private static final short MIN_BALANCE     = (short) 0;

    // Historique
    private static final byte HISTORY_SIZE     = (byte) 10;

    // Status Words personnalisés
    private static final short SW_PIN_VERIFICATION_REQUIRED = (short) 0x6301;
    private static final short SW_INSUFFICIENT_FUNDS        = (short) 0x6985;
    private static final short SW_BALANCE_EXCEEDED          = (short) 0x6A84;
    private static final short SW_INVALID_AMOUNT            = (short) 0x6A80;

    // ═══════════════════════════════════════════════════════════
    // VARIABLES D'INSTANCE (EEPROM - Persistantes)
    // ═══════════════════════════════════════════════════════════

    // PIN utilisateur
    private OwnerPIN userPIN;

    // Balance courante (en unités)
    private short balance;

    // Historique des transactions (valeurs signées)
    // Positif = crédit, Négatif = débit
    private short[] transactionHistory;

    // Index courant dans l'historique (circulaire)
    private byte historyIndex;

    // Nombre total de transactions effectuées
    private short transactionCount;

    // ═══════════════════════════════════════════════════════════
    // CONSTRUCTEUR ET INSTALLATION
    // ═══════════════════════════════════════════════════════════

    /**
     * Constructeur privé - appelé par install()
     * Initialise toutes les variables persistantes
     */
    private EWalletApplet(byte[] bArray, short bOffset, byte bLength) {

        // 1. Créer et initialiser le PIN
        userPIN = new OwnerPIN(PIN_TRY_LIMIT, PIN_MAX_LENGTH);

        // PIN par défaut : "1234"
        byte[] defaultPIN = {0x31, 0x32, 0x33, 0x34};
        userPIN.update(defaultPIN, (short) 0, (byte) defaultPIN.length);

        // 2. Initialiser la balance
        balance = INITIAL_BALANCE;

        // 3. Créer l'historique
        transactionHistory = new short[HISTORY_SIZE];
        historyIndex = 0;
        transactionCount = 0;

        // 4. Enregistrer l'applet
        register();
    }

    /**
     * Méthode d'installation - Point d'entrée obligatoire
     * Appelée par le Card Manager lors de l'installation
     */
    public static void install(byte[] bArray, short bOffset, byte bLength) {
        new EWalletApplet(bArray, bOffset, bLength);
    }

    /**
     * Appelée à chaque sélection de l'applet
     */
    public boolean select() {
        // Réinitialiser le PIN validé (sécurité)
        // L'utilisateur doit se ré-authentifier à chaque session
        if (userPIN.isValidated()) {
            userPIN.reset();
        }
        return true;
    }

    /**
     * Appelée à la désélection de l'applet
     */
    public void deselect() {
        // Invalider le PIN (fin de session)
        userPIN.reset();
    }

    // ═══════════════════════════════════════════════════════════
    // TRAITEMENT DES COMMANDES (process)
    // ═══════════════════════════════════════════════════════════

    /**
     * Point d'entrée principal pour toutes les commandes APDU
     */
    public void process(APDU apdu) {
        // Ignorer la commande SELECT (gérée automatiquement)
        if (selectingApplet()) {
            return;
        }

        byte[] buffer = apdu.getBuffer();
        byte ins = buffer[ISO7816.OFFSET_INS];

        // Dispatcher selon l'instruction
        switch (ins) {
            case INS_VERIFY_PIN:
                processVerifyPIN(apdu);
                break;

            case INS_CREDIT:
                processCredit(apdu);
                break;

            case INS_DEBIT:
                processDebit(apdu);
                break;

            case INS_GET_BALANCE:
                processGetBalance(apdu);
                break;

            case INS_GET_HISTORY:
                processGetHistory(apdu);
                break;

            case INS_CHANGE_PIN:
                processChangePIN(apdu);
                break;

            default:
                ISOException.throwIt(ISO7816.SW_INS_NOT_SUPPORTED);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // COMMANDE : VERIFY PIN (INS = 0x20)
    // ═══════════════════════════════════════════════════════════

    /**
     * Vérifie le PIN utilisateur
     *
     * APDU: 00 20 00 00 [Lc] [PIN]
     * Réponse: 90 00 (succès) ou 63 Cx (échec, x essais restants)
     */
    private void processVerifyPIN(APDU apdu) {
        byte[] buffer = apdu.getBuffer();

        // Recevoir les données
        byte bytesRead = (byte) apdu.setIncomingAndReceive();

        // Valider la longueur du PIN
        if (bytesRead < PIN_MIN_LENGTH || bytesRead > PIN_MAX_LENGTH) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        // Vérifier si le PIN est bloqué
        if (userPIN.getTriesRemaining() == 0) {
            ISOException.throwIt(ISO7816.SW_AUTHENTICATION_METHOD_BLOCKED);
        }

        // Vérifier le PIN
        if (!userPIN.check(buffer, ISO7816.OFFSET_CDATA, bytesRead)) {
            // PIN incorrect
            byte remaining = userPIN.getTriesRemaining();

            if (remaining == 0) {
                // PIN bloqué après cette tentative
                ISOException.throwIt(ISO7816.SW_AUTHENTICATION_METHOD_BLOCKED);
            } else {
                // Retourner le nombre d'essais restants
                // Format: 63 Cx où x = essais restants
                ISOException.throwIt((short) (0x63C0 | remaining));
            }
        }

        // PIN correct - succès implicite (90 00)
    }

    // ═══════════════════════════════════════════════════════════
    // COMMANDE : CREDIT (INS = 0x30)
    // ═══════════════════════════════════════════════════════════

    /**
     * Ajoute des fonds au portefeuille
     *
     * APDU: 80 30 00 00 02 [Montant sur 2 bytes]
     * Montant en big-endian (ex: 00 64 = 100)
     *
     * Prérequis: PIN vérifié
     */
    private void processCredit(APDU apdu) {
        // Vérifier l'authentification
        checkAuthentication();

        byte[] buffer = apdu.getBuffer();

        // Valider Lc
        byte lc = buffer[ISO7816.OFFSET_LC];
        if (lc != 2) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        // Recevoir les données
        apdu.setIncomingAndReceive();

        // Extraire le montant (big-endian)
        short amount = Util.getShort(buffer, ISO7816.OFFSET_CDATA);

        // Valider le montant
        if (amount <= 0) {
            ISOException.throwIt(SW_INVALID_AMOUNT);
        }

        // Vérifier le dépassement de la balance max
        if ((short)(balance + amount) > MAX_BALANCE ||
            (short)(balance + amount) < balance) { // Overflow check
            ISOException.throwIt(SW_BALANCE_EXCEEDED);
        }

        // Transaction atomique
        JCSystem.beginTransaction();
        try {
            // Mettre à jour la balance
            balance = (short)(balance + amount);

            // Ajouter à l'historique (valeur positive = crédit)
            addToHistory(amount);

            // Valider la transaction
            JCSystem.commitTransaction();

        } catch (Exception e) {
            // Annuler en cas d'erreur
            JCSystem.abortTransaction();
            ISOException.throwIt(ISO7816.SW_UNKNOWN);
        }

        // Succès (90 00)
    }

    // ═══════════════════════════════════════════════════════════
    // COMMANDE : DEBIT (INS = 0x40)
    // ═══════════════════════════════════════════════════════════

    /**
     * Retire des fonds du portefeuille
     *
     * APDU: 80 40 00 00 02 [Montant sur 2 bytes]
     *
     * Prérequis: PIN vérifié, fonds suffisants
     */
    private void processDebit(APDU apdu) {
        // Vérifier l'authentification
        checkAuthentication();

        byte[] buffer = apdu.getBuffer();

        // Valider Lc
        byte lc = buffer[ISO7816.OFFSET_LC];
        if (lc != 2) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        // Recevoir les données
        apdu.setIncomingAndReceive();

        // Extraire le montant
        short amount = Util.getShort(buffer, ISO7816.OFFSET_CDATA);

        // Valider le montant
        if (amount <= 0) {
            ISOException.throwIt(SW_INVALID_AMOUNT);
        }

        // Vérifier les fonds suffisants
        if (amount > balance) {
            ISOException.throwIt(SW_INSUFFICIENT_FUNDS);
        }

        // Transaction atomique
        JCSystem.beginTransaction();
        try {
            // Mettre à jour la balance
            balance = (short)(balance - amount);

            // Ajouter à l'historique (valeur négative = débit)
            addToHistory((short)(-amount));

            // Valider
            JCSystem.commitTransaction();

        } catch (Exception e) {
            JCSystem.abortTransaction();
            ISOException.throwIt(ISO7816.SW_UNKNOWN);
        }

        // Succès (90 00)
    }

    // ═══════════════════════════════════════════════════════════
    // COMMANDE : GET BALANCE (INS = 0x50)
    // ═══════════════════════════════════════════════════════════

    /**
     * Retourne la balance courante
     *
     * APDU: 80 50 00 00 02
     * Réponse: [Balance 2 bytes] 90 00
     *
     * Prérequis: PIN vérifié
     */
    private void processGetBalance(APDU apdu) {
        // Vérifier l'authentification
        checkAuthentication();

        byte[] buffer = apdu.getBuffer();

        // Écrire la balance dans le buffer (big-endian)
        Util.setShort(buffer, (short) 0, balance);

        // Envoyer la réponse (2 bytes)
        apdu.setOutgoingAndSend((short) 0, (short) 2);
    }

    // ═══════════════════════════════════════════════════════════
    // COMMANDE : GET HISTORY (INS = 0x60)
    // ═══════════════════════════════════════════════════════════

    /**
     * Retourne l'historique des 10 dernières transactions
     *
     * APDU: 80 60 00 00 14
     * Réponse: [10 x short] 90 00 (20 bytes)
     *
     * Les valeurs sont signées :
     * - Positif = crédit
     * - Négatif = débit
     * - 0 = pas de transaction
     *
     * Prérequis: PIN vérifié
     */
    private void processGetHistory(APDU apdu) {
        // Vérifier l'authentification
        checkAuthentication();

        byte[] buffer = apdu.getBuffer();

        // Copier l'historique dans le buffer
        // On commence par la transaction la plus récente
        short offset = 0;
        byte idx = historyIndex;

        for (byte i = 0; i < HISTORY_SIZE; i++) {
            // Reculer d'une position (buffer circulaire)
            idx = (byte)((idx - 1 + HISTORY_SIZE) % HISTORY_SIZE);

            // Écrire la valeur
            Util.setShort(buffer, offset, transactionHistory[idx]);
            offset += 2;
        }

        // Envoyer la réponse (20 bytes = 10 transactions × 2 bytes)
        apdu.setOutgoingAndSend((short) 0, (short)(HISTORY_SIZE * 2));
    }

    // ═══════════════════════════════════════════════════════════
    // COMMANDE : CHANGE PIN (INS = 0x70)
    // ═══════════════════════════════════════════════════════════

    /**
     * Change le PIN utilisateur
     *
     * APDU: 80 70 00 00 [Lc] [Ancien PIN][Nouveau PIN]
     * Format: [len_old (1)] [old_pin] [len_new (1)] [new_pin]
     *
     * Exemple: 80 70 00 00 0A 04 31323334 04 35363738
     *          = Changer de "1234" à "5678"
     */
    private void processChangePIN(APDU apdu) {
        byte[] buffer = apdu.getBuffer();

        // Recevoir les données
        byte bytesRead = (byte) apdu.setIncomingAndReceive();

        if (bytesRead < 4) { // Minimum: 1 + 1 + 1 + 1 (deux PINs de 1 char)
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        short offset = ISO7816.OFFSET_CDATA;

        // Lire longueur ancien PIN
        byte oldLen = buffer[offset++];
        if (oldLen < PIN_MIN_LENGTH || oldLen > PIN_MAX_LENGTH) {
            ISOException.throwIt(ISO7816.SW_WRONG_DATA);
        }

        // Vérifier l'ancien PIN
        if (!userPIN.check(buffer, offset, oldLen)) {
            byte remaining = userPIN.getTriesRemaining();
            if (remaining == 0) {
                ISOException.throwIt(ISO7816.SW_AUTHENTICATION_METHOD_BLOCKED);
            }
            ISOException.throwIt((short)(0x63C0 | remaining));
        }

        offset += oldLen;

        // Lire longueur nouveau PIN
        byte newLen = buffer[offset++];
        if (newLen < PIN_MIN_LENGTH || newLen > PIN_MAX_LENGTH) {
            ISOException.throwIt(ISO7816.SW_WRONG_DATA);
        }

        // Mettre à jour le PIN (transaction atomique implicite)
        userPIN.update(buffer, offset, newLen);

        // Succès (90 00)
    }

    // ═══════════════════════════════════════════════════════════
    // MÉTHODES UTILITAIRES PRIVÉES
    // ═══════════════════════════════════════════════════════════

    /**
     * Vérifie que l'utilisateur est authentifié
     * Lève une exception si non authentifié
     */
    private void checkAuthentication() {
        if (!userPIN.isValidated()) {
            ISOException.throwIt(ISO7816.SW_SECURITY_STATUS_NOT_SATISFIED);
        }
    }

    /**
     * Ajoute une transaction à l'historique (buffer circulaire)
     * @param amount Montant signé (+ = crédit, - = débit)
     */
    private void addToHistory(short amount) {
        transactionHistory[historyIndex] = amount;
        historyIndex = (byte)((historyIndex + 1) % HISTORY_SIZE);
        transactionCount++;
    }
}
```