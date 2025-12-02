/*
 * CounterApplet.java - Applet de compteur JavaCard
 *
 * Cet applet démontre:
 * - Gestion d'un compteur persistant
 * - Opérations arithmétiques sécurisées
 * - Gestion de limites et seuils
 *
 * AID: F0 00 00 00 01 00 02
 */
package com.example.counter;

import javacard.framework.*;

public class CounterApplet extends Applet {

    // ============================================
    // CONSTANTES APDU
    // ============================================

    // CLA propriétaire
    private static final byte CLA_COUNTER = (byte) 0x80;

    // Instructions
    private static final byte INS_GET_COUNTER = (byte) 0x10;     // Lire le compteur
    private static final byte INS_INCREMENT = (byte) 0x11;       // Incrémenter (+1 ou +P1)
    private static final byte INS_DECREMENT = (byte) 0x12;       // Décrémenter (-1 ou -P1)
    private static final byte INS_RESET = (byte) 0x13;           // Remettre à zéro
    private static final byte INS_SET_VALUE = (byte) 0x14;       // Définir une valeur
    private static final byte INS_SET_LIMIT = (byte) 0x15;       // Définir une limite max
    private static final byte INS_GET_INFO = (byte) 0x16;        // Obtenir les infos complètes
    private static final byte INS_ADD_VALUE = (byte) 0x17;       // Ajouter une valeur (dans data)
    private static final byte INS_SUB_VALUE = (byte) 0x18;       // Soustraire une valeur (dans data)
    private static final byte INS_MULTIPLY = (byte) 0x19;        // Multiplier par une valeur (P1)

    // ============================================
    // DONNÉES PERSISTANTES (EEPROM)
    // ============================================

    // Compteur principal (4 bytes pour un entier 32 bits)
    private byte[] counter;

    // Limite maximale du compteur
    private byte[] maxLimit;

    // Compteur d'opérations effectuées
    private short operationCount;

    // Flag: limite activée
    private boolean limitEnabled;

    // ============================================
    // CONSTRUCTEUR ET INSTALLATION
    // ============================================

    private CounterApplet() {
        // Initialiser le compteur à 0
        counter = new byte[4];
        Util.arrayFillNonAtomic(counter, (short) 0, (short) 4, (byte) 0);

        // Limite par défaut: 0x7FFFFFFF (max int positif)
        maxLimit = new byte[4];
        maxLimit[0] = (byte) 0x7F;
        maxLimit[1] = (byte) 0xFF;
        maxLimit[2] = (byte) 0xFF;
        maxLimit[3] = (byte) 0xFF;

        limitEnabled = false;
        operationCount = 0;

        register();
    }

    public static void install(byte[] bArray, short bOffset, byte bLength) {
        new CounterApplet();
    }

    public boolean select() {
        // L'applet peut toujours être sélectionné
        return true;
    }

    public void deselect() {
        // Rien à faire lors de la désélection
    }

    // ============================================
    // TRAITEMENT DES COMMANDES
    // ============================================

    public void process(APDU apdu) {
        byte[] buffer = apdu.getBuffer();

        // Ignorer SELECT
        if (selectingApplet()) {
            return;
        }
        

        // Vérifier CLA
        if (buffer[ISO7816.OFFSET_CLA] != CLA_COUNTER) {
            ISOException.throwIt(ISO7816.SW_CLA_NOT_SUPPORTED);
        }

        // Dispatcher
        switch (buffer[ISO7816.OFFSET_INS]) {
            // case (byte) 0xA4:
                
            //     break;
            case INS_GET_COUNTER:
                processGetCounter(apdu);
                break;
            case INS_INCREMENT:
                processIncrement(apdu);
                break;
            case INS_DECREMENT:
                processDecrement(apdu);
                break;
            case INS_RESET:
                processReset(apdu);
                break;
            case INS_SET_VALUE:
                processSetValue(apdu);
                break;
            case INS_SET_LIMIT:
                processSetLimit(apdu);
                break;
            case INS_GET_INFO:
                processGetInfo(apdu);
                break;
            case INS_ADD_VALUE:
                processAddValue(apdu);
                break;
            case INS_SUB_VALUE:
                processSubValue(apdu);
                break;
            case INS_MULTIPLY:
                processMultiply(apdu);
                break;
            default:
                ISOException.throwIt(ISO7816.SW_INS_NOT_SUPPORTED);
        }

        operationCount++;
    }

    // ============================================
    // HANDLERS D'INSTRUCTIONS
    // ============================================

    /**
     * INS 10: Retourne la valeur du compteur (4 bytes big-endian)
     * APDU: 80 10 00 00 04
     */
    private void processGetCounter(APDU apdu) {
        byte[] buffer = apdu.getBuffer();

        Util.arrayCopyNonAtomic(counter, (short) 0, buffer, (short) 0, (short) 4);
        apdu.setOutgoingAndSend((short) 0, (short) 4);
    }

    /**
     * INS 11: Incrémente le compteur
     * P1 = valeur à ajouter (0 = +1)
     * APDU: 80 11 05 00 00 -> ajoute 5
     */
    private void processIncrement(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        byte p1 = buffer[ISO7816.OFFSET_P1];

        short increment = (p1 == 0) ? (short) 1 : (short) (p1 & 0xFF);

        if (!addToCounter(increment)) {
            ISOException.throwIt(ISO7816.SW_CONDITIONS_NOT_SATISFIED);
        }

        // Retourner la nouvelle valeur
        Util.arrayCopyNonAtomic(counter, (short) 0, buffer, (short) 0, (short) 4);
        apdu.setOutgoingAndSend((short) 0, (short) 4);
    }

    /**
     * INS 12: Décrémente le compteur
     * P1 = valeur à soustraire (0 = -1)
     * APDU: 80 12 03 00 00 -> soustrait 3
     */
    private void processDecrement(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        byte p1 = buffer[ISO7816.OFFSET_P1];

        short decrement = (p1 == 0) ? (short) 1 : (short) (p1 & 0xFF);

        if (!subtractFromCounter(decrement)) {
            ISOException.throwIt(ISO7816.SW_CONDITIONS_NOT_SATISFIED);
        }

        // Retourner la nouvelle valeur
        Util.arrayCopyNonAtomic(counter, (short) 0, buffer, (short) 0, (short) 4);
        apdu.setOutgoingAndSend((short) 0, (short) 4);
    }

    /**
     * INS 13: Remet le compteur à zéro
     * APDU: 80 13 00 00 00
     */
    private void processReset(APDU apdu) {
        Util.arrayFillNonAtomic(counter, (short) 0, (short) 4, (byte) 0);
    }

    /**
     * INS 14: Définit une valeur spécifique
     * Data: 4 bytes big-endian
     * APDU: 80 14 00 00 04 [00 00 00 64] -> set to 100
     */
    private void processSetValue(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        short bytesRead = apdu.setIncomingAndReceive();

        if (bytesRead != 4) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        // Vérifier la limite si activée
        if (limitEnabled && compareArrays(buffer, ISO7816.OFFSET_CDATA, maxLimit, (short) 0, (short) 4) > 0) {
            ISOException.throwIt(ISO7816.SW_CONDITIONS_NOT_SATISFIED);
        }

        Util.arrayCopyNonAtomic(buffer, ISO7816.OFFSET_CDATA, counter, (short) 0, (short) 4);
    }

    /**
     * INS 15: Définit la limite maximale
     * P1 = 01 pour activer, 00 pour désactiver
     * Data: 4 bytes big-endian (nouvelle limite)
     * APDU: 80 15 01 00 04 [00 00 03 E8] -> limite à 1000
     */
    private void processSetLimit(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        byte p1 = buffer[ISO7816.OFFSET_P1];

        short bytesRead = apdu.setIncomingAndReceive();

        if (bytesRead != 4) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        Util.arrayCopyNonAtomic(buffer, ISO7816.OFFSET_CDATA, maxLimit, (short) 0, (short) 4);
        limitEnabled = (p1 == 0x01);
    }

    /**
     * INS 16: Retourne les informations complètes
     * Réponse: counter(4) + limit(4) + limitEnabled(1) + opCount(2) = 11 bytes
     * APDU: 80 16 00 00 0B
     */
    private void processGetInfo(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        short offset = 0;

        // Compteur actuel
        Util.arrayCopyNonAtomic(counter, (short) 0, buffer, offset, (short) 4);
        offset += 4;

        // Limite
        Util.arrayCopyNonAtomic(maxLimit, (short) 0, buffer, offset, (short) 4);
        offset += 4;

        // Limite activée
        buffer[offset++] = limitEnabled ? (byte) 0x01 : (byte) 0x00;

        // Nombre d'opérations
        Util.setShort(buffer, offset, operationCount);
        offset += 2;

        apdu.setOutgoingAndSend((short) 0, offset);
    }

    /**
     * INS 17: Ajoute une valeur (2 bytes dans data)
     * APDU: 80 17 00 00 02 [01 00] -> ajoute 256
     */
    private void processAddValue(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        short bytesRead = apdu.setIncomingAndReceive();

        if (bytesRead != 2) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        short value = Util.getShort(buffer, ISO7816.OFFSET_CDATA);

        if (!addToCounter(value)) {
            ISOException.throwIt(ISO7816.SW_CONDITIONS_NOT_SATISFIED);
        }

        // Retourner la nouvelle valeur
        Util.arrayCopyNonAtomic(counter, (short) 0, buffer, (short) 0, (short) 4);
        apdu.setOutgoingAndSend((short) 0, (short) 4);
    }

    /**
     * INS 18: Soustrait une valeur (2 bytes dans data)
     * APDU: 80 18 00 00 02 [00 32] -> soustrait 50
     */
    private void processSubValue(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        short bytesRead = apdu.setIncomingAndReceive();

        if (bytesRead != 2) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }

        short value = Util.getShort(buffer, ISO7816.OFFSET_CDATA);

        if (!subtractFromCounter(value)) {
            ISOException.throwIt(ISO7816.SW_CONDITIONS_NOT_SATISFIED);
        }

        // Retourner la nouvelle valeur
        Util.arrayCopyNonAtomic(counter, (short) 0, buffer, (short) 0, (short) 4);
        apdu.setOutgoingAndSend((short) 0, (short) 4);
    }

    /**
     * INS 19: Multiplie le compteur par une valeur
     * P1 = multiplicateur (1-255, 0 = x2)
     * APDU: 80 19 03 00 04 -> multiplie par 3
     */
    private void processMultiply(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        byte p1 = buffer[ISO7816.OFFSET_P1];

        // Multiplicateur: si P1=0, on multiplie par 2
        int multiplier = (p1 == 0) ? 2 : (p1 & 0xFF);

        if (!multiplyCounter(multiplier)) {
            ISOException.throwIt(ISO7816.SW_CONDITIONS_NOT_SATISFIED);
        }

        // Retourner la nouvelle valeur
        Util.arrayCopyNonAtomic(counter, (short) 0, buffer, (short) 0, (short) 4);
        apdu.setOutgoingAndSend((short) 0, (short) 4);
    }

    // ============================================
    // MÉTHODES UTILITAIRES
    // ============================================

    /**
     * Ajoute une valeur au compteur (gestion 32 bits)
     */
    private boolean addToCounter(short value) {
        // Conversion en valeur 32 bits
        int currentValue = getCounterAsInt();
        int newValue = currentValue + (value & 0xFFFF);

        // Vérifier overflow et limite
        if (newValue < currentValue) {
            return false; // Overflow
        }

        if (limitEnabled && newValue > getLimitAsInt()) {
            return false; // Dépasse la limite
        }

        setCounterFromInt(newValue);
        return true;
    }

    /**
     * Soustrait une valeur du compteur
     */
    private boolean subtractFromCounter(short value) {
        int currentValue = getCounterAsInt();
        int newValue = currentValue - (value & 0xFFFF);

        // Vérifier underflow
        if (newValue < 0) {
            return false;
        }

        setCounterFromInt(newValue);
        return true;
    }

    /**
     * Multiplie le compteur par une valeur
     */
    private boolean multiplyCounter(int multiplier) {
        int currentValue = getCounterAsInt();
        long newValue = (long) currentValue * multiplier;

        // Vérifier overflow (> 32 bits)
        if (newValue > 0x7FFFFFFFL) {
            return false;
        }

        // Vérifier la limite
        if (limitEnabled && newValue > getLimitAsInt()) {
            return false;
        }

        setCounterFromInt((int) newValue);
        return true;
    }

    /**
     * Convertit le compteur en int
     */
    private int getCounterAsInt() {
        return ((counter[0] & 0xFF) << 24) |
               ((counter[1] & 0xFF) << 16) |
               ((counter[2] & 0xFF) << 8) |
               (counter[3] & 0xFF);
    }

    /**
     * Convertit la limite en int
     */
    private int getLimitAsInt() {
        return ((maxLimit[0] & 0xFF) << 24) |
               ((maxLimit[1] & 0xFF) << 16) |
               ((maxLimit[2] & 0xFF) << 8) |
               (maxLimit[3] & 0xFF);
    }

    /**
     * Met à jour le compteur depuis un int
     */
    private void setCounterFromInt(int value) {
        counter[0] = (byte) ((value >> 24) & 0xFF);
        counter[1] = (byte) ((value >> 16) & 0xFF);
        counter[2] = (byte) ((value >> 8) & 0xFF);
        counter[3] = (byte) (value & 0xFF);
    }

    /**
     * Compare deux tableaux de bytes
     */
    private byte compareArrays(byte[] a1, short off1, byte[] a2, short off2, short len) {
        for (short i = 0; i < len; i++) {
            short b1 = (short) (a1[(short)(off1 + i)] & 0xFF);
            short b2 = (short) (a2[(short)(off2 + i)] & 0xFF);
            if (b1 > b2) return 1;
            if (b1 < b2) return -1;
        }
        return 0;
    }
}
