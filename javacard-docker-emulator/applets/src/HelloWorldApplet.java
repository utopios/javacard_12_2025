/*
 * HelloWorldApplet.java - Exemple d'applet JavaCard simple
 * 
 * Cet applet démontre les fonctionnalités de base:
 * - Sélection d'applet
 * - Réponse aux commandes APDU
 * - Stockage de données en EEPROM
 * - Gestion de PIN
 * 
 * AID recommandé: F0 00 00 00 01 00 01
 */
package com.example.helloworld;

import javacard.framework.*;
import javacard.security.*;

public class HelloWorldApplet extends Applet {
    
    // Constantes CLA/INS
    private static final byte CLA_PROPRIETARY = (byte) 0x80;
    
    private static final byte INS_HELLO = (byte) 0x00;      // Retourne "Hello World"
    private static final byte INS_ECHO = (byte) 0x01;       // Echo les données reçues
    private static final byte INS_GET_DATA = (byte) 0x02;   // Lit les données stockées
    private static final byte INS_PUT_DATA = (byte) 0x03;   // Écrit des données
    private static final byte INS_VERIFY_PIN = (byte) 0x20; // Vérifie le PIN
    private static final byte INS_CHANGE_PIN = (byte) 0x24; // Change le PIN
    private static final byte INS_GET_STATUS = (byte) 0xF0; // Statut de l'applet
    
    // Message Hello World
    private static final byte[] HELLO_MSG = {
        'H', 'e', 'l', 'l', 'o', ' ', 'W', 'o', 'r', 'l', 'd', '!'
    };
    
    // Stockage de données (max 256 bytes)
    private byte[] dataStore;
    private short dataLength;
    
    // PIN (4-8 chiffres, 3 essais)
    private OwnerPIN pin;
    private static final byte PIN_TRY_LIMIT = 3;
    private static final byte PIN_MIN_LENGTH = 4;
    private static final byte PIN_MAX_LENGTH = 8;
    
    // PIN par défaut: 1234
    private static final byte[] DEFAULT_PIN = { 0x31, 0x32, 0x33, 0x34 };
    
    // Compteur d'utilisation
    private short usageCounter;
    
    /**
     * Constructeur privé - appelé par install()
     */
    private HelloWorldApplet(byte[] bArray, short bOffset, byte bLength) {
        // Initialiser le stockage de données
        dataStore = new byte[256];
        dataLength = 0;
        
        // Initialiser le PIN
        pin = new OwnerPIN(PIN_TRY_LIMIT, PIN_MAX_LENGTH);
        pin.update(DEFAULT_PIN, (short) 0, (byte) DEFAULT_PIN.length);
        
        // Compteur
        usageCounter = 0;
        
        // Enregistrer l'applet
        register();
    }
    
    /**
     * Méthode d'installation appelée par le JCRE
     */
    public static void install(byte[] bArray, short bOffset, byte bLength) {
        new HelloWorldApplet(bArray, bOffset, bLength);
    }
    
    /**
     * Appelé lors de la sélection de l'applet
     */
    public boolean select() {
        // Réinitialiser l'état PIN si nécessaire
        if (pin.getTriesRemaining() == 0) {
            // PIN bloqué - on pourrait logger ou notifier
        }
        return true;
    }
    
    /**
     * Appelé lors de la désélection de l'applet
     */
    public void deselect() {
        // Réinitialiser l'état d'authentification
        pin.reset();
    }
    
    /**
     * Traitement des commandes APDU
     */
    public void process(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        
        // Ignorer la commande SELECT
        if (selectingApplet()) {
            return;
        }
        
        // Vérifier la classe
        byte cla = buffer[ISO7816.OFFSET_CLA];
        if (cla != CLA_PROPRIETARY && cla != (byte) 0x00) {
            ISOException.throwIt(ISO7816.SW_CLA_NOT_SUPPORTED);
        }
        
        // Incrémenter le compteur
        usageCounter++;
        
        // Dispatcher selon l'instruction
        switch (buffer[ISO7816.OFFSET_INS]) {
            case INS_HELLO:
                processHello(apdu);
                break;
            case INS_ECHO:
                processEcho(apdu);
                break;
            case INS_GET_DATA:
                processGetData(apdu);
                break;
            case INS_PUT_DATA:
                processPutData(apdu);
                break;
            case INS_VERIFY_PIN:
                processVerifyPin(apdu);
                break;
            case INS_CHANGE_PIN:
                processChangePin(apdu);
                break;
            case INS_GET_STATUS:
                processGetStatus(apdu);
                break;
            default:
                ISOException.throwIt(ISO7816.SW_INS_NOT_SUPPORTED);
        }
    }
    
    /**
     * INS 00: Retourne "Hello World!"
     */
    private void processHello(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        
        // Copier le message dans le buffer de sortie
        Util.arrayCopyNonAtomic(HELLO_MSG, (short) 0, buffer, (short) 0, (short) HELLO_MSG.length);
        
        // Envoyer la réponse
        apdu.setOutgoingAndSend((short) 0, (short) HELLO_MSG.length);
    }
    
    /**
     * INS 01: Echo - retourne les données reçues
     */
    private void processEcho(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        
        // Recevoir les données
        short bytesRead = apdu.setIncomingAndReceive();
        
        if (bytesRead == 0) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }
        
        // Retourner les mêmes données
        apdu.setOutgoingAndSend(ISO7816.OFFSET_CDATA, bytesRead);
    }
    
    /**
     * INS 02: Lit les données stockées
     */
    private void processGetData(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        
        if (dataLength == 0) {
            ISOException.throwIt(ISO7816.SW_CONDITIONS_NOT_SATISFIED);
        }
        
        // Copier les données dans le buffer
        Util.arrayCopyNonAtomic(dataStore, (short) 0, buffer, (short) 0, dataLength);
        
        // Envoyer
        apdu.setOutgoingAndSend((short) 0, dataLength);
    }
    
    /**
     * INS 03: Stocke des données (nécessite authentification PIN)
     */
    private void processPutData(APDU apdu) {
        // Vérifier l'authentification
        if (!pin.isValidated()) {
            ISOException.throwIt(ISO7816.SW_SECURITY_STATUS_NOT_SATISFIED);
        }
        
        byte[] buffer = apdu.getBuffer();
        
        // Recevoir les données
        short bytesRead = apdu.setIncomingAndReceive();
        
        if (bytesRead == 0 || bytesRead > 256) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }
        
        // Stocker les données
        Util.arrayCopyNonAtomic(buffer, ISO7816.OFFSET_CDATA, dataStore, (short) 0, bytesRead);
        dataLength = bytesRead;
    }
    
    /**
     * INS 20: Vérifie le PIN
     */
    private void processVerifyPin(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        
        // Recevoir le PIN
        short bytesRead = apdu.setIncomingAndReceive();
        
        if (bytesRead < PIN_MIN_LENGTH || bytesRead > PIN_MAX_LENGTH) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }
        
        // Vérifier le PIN
        if (!pin.check(buffer, ISO7816.OFFSET_CDATA, (byte) bytesRead)) {
            short triesRemaining = pin.getTriesRemaining();
            if (triesRemaining == 0) {
                ISOException.throwIt(ISO7816.SW_FILE_INVALID);
            }
            // SW 63 Cx où x = nombre d'essais restants
            ISOException.throwIt((short) (0x63C0 | triesRemaining));
        }
        
        // PIN correct - SW 9000 implicite
    }
    
    /**
     * INS 24: Change le PIN (format: ancien PIN + nouveau PIN)
     */
    private void processChangePin(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        
        // Recevoir les données
        short bytesRead = apdu.setIncomingAndReceive();
        
        // Format attendu: P2 = longueur ancien PIN
        byte oldPinLength = buffer[ISO7816.OFFSET_P2];
        short newPinLength = (short) (bytesRead - oldPinLength);
        
        if (oldPinLength < PIN_MIN_LENGTH || oldPinLength > PIN_MAX_LENGTH ||
            newPinLength < PIN_MIN_LENGTH || newPinLength > PIN_MAX_LENGTH) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }
        
        // Vérifier l'ancien PIN
        if (!pin.check(buffer, ISO7816.OFFSET_CDATA, oldPinLength)) {
            short triesRemaining = pin.getTriesRemaining();
            ISOException.throwIt((short) (0x63C0 | triesRemaining));
        }
        
        // Mettre à jour avec le nouveau PIN
        pin.update(buffer, (short) (ISO7816.OFFSET_CDATA + oldPinLength), (byte) newPinLength);
    }
    
    /**
     * INS F0: Retourne le statut de l'applet
     */
    private void processGetStatus(APDU apdu) {
        byte[] buffer = apdu.getBuffer();
        short offset = 0;
        
        // Version (2 bytes)
        buffer[offset++] = 0x01;  // Version majeure
        buffer[offset++] = 0x00;  // Version mineure
        
        // Compteur d'utilisation (2 bytes)
        Util.setShort(buffer, offset, usageCounter);
        offset += 2;
        
        // Essais PIN restants (1 byte)
        buffer[offset++] = pin.getTriesRemaining();
        
        // PIN validé (1 byte)
        buffer[offset++] = pin.isValidated() ? (byte) 0x01 : (byte) 0x00;
        
        // Taille des données stockées (2 bytes)
        Util.setShort(buffer, offset, dataLength);
        offset += 2;
        
        // Envoyer
        apdu.setOutgoingAndSend((short) 0, offset);
    }
}
