
package com.example.monapplet;

import javacard.framework.*;

public class MonApplet extends Applet {

    private static final byte INS_COMMAND_ZERO = (byte) 0x00;

    private MonApplet() {
        // Initialisation de l'applet
        register();
    }

    public static void install(byte[] bArray, short bOffset, byte bLength) {
        new MonApplet();
    }

    public void process(APDU apdu) {
        // Traiter les commandes APDU ici
        byte[] buffer = apdu.getBuffer();

        if(selectingApplet()) {
            return;
        }

        if(buffer[ISO7816.OFFSET_CLA] != (byte) 0x00) {
            ISOException.throwIt(ISO7816.SW_CLA_NOT_SUPPORTED);
        }   

        switch(buffer[ISO7816.OFFSET_INS]) {
            case INS_COMMAND_ZERO:
                handleCommandZero(apdu);
                break;
            default:
                ISOException.throwIt(ISO7816.SW_INS_NOT_SUPPORTED);
        }

        
    }

    public void handleCommandZero(APDU apdu) {
        // Logique pour la commande INS_COMMAND_ZERO
        // Par exemple, on peut simplement renvoyer un message de succès
        byte[] buffer = apdu.getBuffer();
        apdu.setOutgoing();
        apdu.setOutgoingLength((short) 2);
        buffer[0] = (byte) 0x90; // SW1
        buffer[1] = (byte) 0x00; // SW2
        apdu.sendBytes((short) 0, (short) 2);
    }
}