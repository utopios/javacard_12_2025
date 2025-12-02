package com.example.smartcardio;

import javax.smartcardio.*;
import java.util.List;
import java.util.Scanner;

public class SmartCardInteractiveApp {

    // Scanner pour entrées utilisateur
    private static Scanner scanner = new Scanner(System.in);

    // Connexion courante
    private static Card card = null;
    private static CardChannel channel = null;

    public static void main(String[] args) {
        System.out.println("╔════════════════════════════════════════════╗");
        System.out.println("║   Application Smart Card Interactive        ║");
        System.out.println("╚════════════════════════════════════════════╝");
        System.out.println();

        try {
            // Étape 1 : Lister et sélectionner un lecteur
            CardTerminal terminal = selectReader();
            if (terminal == null) {
                System.err.println("Aucun lecteur sélectionné. Fin du programme.");
                return;
            }

            // Étape 2 : Attendre et connecter à la carte
            connectToCard(terminal);

            // Étape 3 : Sélectionner une applet
            if (!selectApplet()) {
                System.out.println("Sélection applet échouée ou annulée.");
            }

            // Étape 4 : Vérifier le PIN
            if (!verifyPIN()) {
                System.out.println("Authentification échouée.");
            } else {
                System.out.println("✓ Authentification réussie !");

                // Étape 5 : Mode interactif
                interactiveMode();
            }

        } catch (Exception e) {
            System.err.println("Erreur: " + e.getMessage());
            e.printStackTrace();
        } finally {
            // Étape 6 : Déconnexion propre
            disconnect();
        }

        System.out.println("\nProgramme terminé.");
    }

    /**
     * Étape 1 : Liste les lecteurs et permet la sélection
     */
    private static CardTerminal selectReader() throws CardException {
        System.out.println("═══ Étape 1 : Sélection du lecteur ═══\n");

        // Obtenir la factory PC/SC
        TerminalFactory factory = TerminalFactory.getDefault();
        CardTerminals terminals = factory.terminals();

        // Lister les lecteurs
        List<CardTerminal> readerList;
        try {
            readerList = terminals.list();
        } catch (CardException e) {
            System.err.println("Impossible de lister les lecteurs.");
            System.err.println("Vérifiez que le service PC/SC est démarré.");
            return null;
        }

        if (readerList.isEmpty()) {
            System.err.println("Aucun lecteur de carte détecté !");
            return null;
        }

        // Afficher les lecteurs
        System.out.println("Lecteurs disponibles :");
        System.out.println("─────────────────────────────────────────");
        for (int i = 0; i < readerList.size(); i++) {
            CardTerminal t = readerList.get(i);
            String status = t.isCardPresent() ? "[Carte présente]" : "[Vide]";
            System.out.printf("  %d. %s %s%n", i + 1, t.getName(), status);
        }
        System.out.println("─────────────────────────────────────────");

        // Sélection par l'utilisateur
        System.out.print("\nSélectionnez un lecteur (1-" + readerList.size() + ") : ");
        int choice = readInt(1, readerList.size());

        CardTerminal selected = readerList.get(choice - 1);
        System.out.println("→ Lecteur sélectionné : " + selected.getName());

        return selected;
    }

    /**
     * Étape 2 : Attend la carte et se connecte
     */
    private static void connectToCard(CardTerminal terminal) throws CardException {
        System.out.println("\n═══ Étape 2 : Connexion à la carte ═══\n");

        // Vérifier présence carte
        if (!terminal.isCardPresent()) {
            System.out.println("En attente d'une carte...");
            System.out.println("(Insérez une carte dans le lecteur)");

            // Attendre indéfiniment
            boolean inserted = terminal.waitForCardPresent(0);
            if (!inserted) {
                throw new CardException("Timeout en attente de carte");
            }
            System.out.println("→ Carte détectée !");
        } else {
            System.out.println("Carte déjà présente dans le lecteur.");
        }

        // Connexion
        System.out.println("Connexion en cours...");
        card = terminal.connect("*"); // Auto-négociation protocole
        channel = card.getBasicChannel();

        // Afficher informations
        System.out.println("→ Connecté !");
        System.out.println("  Protocole : " + card.getProtocol());

        // Afficher ATR
        ATR atr = card.getATR();
        System.out.println("  ATR : " + bytesToHex(atr.getBytes()));
        System.out.println("  ATR historiques : " + bytesToHex(atr.getHistoricalBytes()));
    }

    /**
     * Étape 3 : Sélectionne une applet par AID
     */
    private static boolean selectApplet() throws CardException {
        System.out.println("\n═══ Étape 3 : Sélection de l'applet ═══\n");

        System.out.println("Entrez l'AID de l'applet (hex, ex: A0000000010101)");
        System.out.println("Ou appuyez sur Entrée pour sauter cette étape.");
        System.out.print("AID : ");

        String aidHex = scanner.nextLine().trim().replaceAll("\\s+", "");

        if (aidHex.isEmpty()) {
            System.out.println("→ Sélection d'applet ignorée.");
            return false;
        }

        // Convertir hex en bytes
        byte[] aid;
        try {
            aid = hexToBytes(aidHex);
        } catch (IllegalArgumentException e) {
            System.err.println("AID invalide : " + e.getMessage());
            return false;
        }

        // Construire APDU SELECT
        // 00 A4 04 00 [Lc] [AID]
        CommandAPDU selectCmd = new CommandAPDU(
            0x00,       // CLA
            0xA4,       // INS = SELECT
            0x04,       // P1 = Select by DF name
            0x00,       // P2 = First occurrence
            aid         // Data = AID
        );

        System.out.println("Envoi : " + bytesToHex(selectCmd.getBytes()));

        // Envoyer
        ResponseAPDU response = channel.transmit(selectCmd);

        System.out.println("Réponse : " + bytesToHex(response.getBytes()));
        System.out.println("SW : " + String.format("%04X", response.getSW()));

        if (response.getSW() == 0x9000) {
            System.out.println("→ Applet sélectionnée avec succès !");
            if (response.getData().length > 0) {
                System.out.println("  FCI : " + bytesToHex(response.getData()));
            }
            return true;
        } else {
            System.out.println("→ Échec sélection : " + swToString(response.getSW()));
            return false;
        }
    }

    /**
     * Étape 4 : Vérifie le PIN utilisateur
     */
    private static boolean verifyPIN() throws CardException {
        System.out.println("\n═══ Étape 4 : Vérification du PIN ═══\n");

        System.out.println("Entrez le PIN (ou Entrée pour sauter) :");
        System.out.print("PIN : ");

        String pin = scanner.nextLine().trim();

        if (pin.isEmpty()) {
            System.out.println("→ Vérification PIN ignorée.");
            return false;
        }

        // Convertir PIN en bytes ASCII
        byte[] pinBytes = pin.getBytes();

        // Construire APDU VERIFY
        // 00 20 00 00 [Lc] [PIN]
        // Note: P2 = 0x00 ou 0x01 selon l'applet (référence PIN)

        System.out.print("Référence PIN (P2, défaut=0x01) : ");
        String p2Str = scanner.nextLine().trim();
        byte p2 = 0x01;
        if (!p2Str.isEmpty()) {
            p2 = (byte) Integer.parseInt(p2Str.replace("0x", ""), 16);
        }

        CommandAPDU verifyCmd = new CommandAPDU(
            0x00,       // CLA
            0x20,       // INS = VERIFY
            0x00,       // P1
            p2,         // P2 = PIN reference
            pinBytes    // Data = PIN
        );

        System.out.println("Envoi : " + bytesToHex(verifyCmd.getBytes()));

        // Envoyer
        ResponseAPDU response = channel.transmit(verifyCmd);

        System.out.println("SW : " + String.format("%04X", response.getSW()));

        if (response.getSW() == 0x9000) {
            return true;
        } else if ((response.getSW() & 0xFFF0) == 0x63C0) {
            int tries = response.getSW() & 0x000F;
            System.out.println("→ PIN incorrect ! " + tries + " essai(s) restant(s)");
            return false;
        } else {
            System.out.println("→ Erreur : " + swToString(response.getSW()));
            return false;
        }
    }

    /**
     * Étape 5 : Mode interactif pour envoyer des APDU
     */
    private static void interactiveMode() throws CardException {
        System.out.println("\n═══ Étape 5 : Mode interactif ═══\n");
        System.out.println("Entrez des commandes APDU en hexadécimal.");
        System.out.println("Exemples :");
        System.out.println("  00A4040007F0000000010001    (SELECT)");
        System.out.println("  80500000                    (GET INFO)");
        System.out.println("Tapez 'quit' ou 'exit' pour terminer.\n");

        while (true) {
            System.out.print("APDU> ");
            String input = scanner.nextLine().trim();

            // Commandes de sortie
            if (input.equalsIgnoreCase("quit") ||
                input.equalsIgnoreCase("exit") ||
                input.equalsIgnoreCase("q")) {
                break;
            }

            // Ignorer lignes vides
            if (input.isEmpty()) {
                continue;
            }

            // Aide
            if (input.equalsIgnoreCase("help") || input.equals("?")) {
                printHelp();
                continue;
            }

            // Parser et envoyer APDU
            try {
                byte[] apduBytes = hexToBytes(input.replaceAll("\\s+", ""));

                if (apduBytes.length < 4) {
                    System.out.println("Erreur: APDU trop courte (min 4 bytes)");
                    continue;
                }

                CommandAPDU cmd = new CommandAPDU(apduBytes);
                System.out.println("→ Envoi : " + bytesToHex(cmd.getBytes()));

                ResponseAPDU resp = channel.transmit(cmd);

                System.out.println("← Réponse :");
                if (resp.getData().length > 0) {
                    System.out.println("   Data : " + bytesToHex(resp.getData()));
                    System.out.println("   ASCII: " + tryDecodeAscii(resp.getData()));
                }
                System.out.println("   SW   : " + String.format("%04X", resp.getSW()) +
                                   " (" + swToString(resp.getSW()) + ")");
                System.out.println();

            } catch (IllegalArgumentException e) {
                System.out.println("Erreur de format : " + e.getMessage());
            } catch (CardException e) {
                System.out.println("Erreur carte : " + e.getMessage());
            }
        }

        System.out.println("Fin du mode interactif.");
    }

    /**
     * Étape 6 : Déconnexion propre
     */
    private static void disconnect() {
        System.out.println("\n═══ Déconnexion ═══");

        if (card != null) {
            try {
                card.disconnect(false); // false = ne pas reset la carte
                System.out.println("→ Carte déconnectée proprement.");
            } catch (CardException e) {
                System.err.println("Erreur déconnexion : " + e.getMessage());
            }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // Méthodes utilitaires
    // ═══════════════════════════════════════════════════════════

    /**
     * Convertit un tableau de bytes en chaîne hexadécimale
     */
    private static String bytesToHex(byte[] bytes) {
        if (bytes == null || bytes.length == 0) {
            return "(vide)";
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02X ", b));
        }
        return sb.toString().trim();
    }

    /**
     * Convertit une chaîne hexadécimale en tableau de bytes
     */
    private static byte[] hexToBytes(String hex) {
        hex = hex.replaceAll("\\s+", "");
        if (hex.length() % 2 != 0) {
            throw new IllegalArgumentException("Longueur impaire");
        }

        byte[] result = new byte[hex.length() / 2];
        for (int i = 0; i < result.length; i++) {
            int idx = i * 2;
            result[i] = (byte) Integer.parseInt(hex.substring(idx, idx + 2), 16);
        }
        return result;
    }

    /**
     * Lit un entier dans une plage donnée
     */
    private static int readInt(int min, int max) {
        while (true) {
            try {
                String input = scanner.nextLine().trim();
                int value = Integer.parseInt(input);
                if (value >= min && value <= max) {
                    return value;
                }
                System.out.print("Valeur hors plage. Réessayez : ");
            } catch (NumberFormatException e) {
                System.out.print("Nombre invalide. Réessayez : ");
            }
        }
    }

    /**
     * Convertit un Status Word en description textuelle
     */
    private static String swToString(int sw) {
        switch (sw) {
            case 0x9000: return "Succès";
            case 0x6700: return "Longueur incorrecte";
            case 0x6982: return "Sécurité non satisfaite";
            case 0x6983: return "Authentification bloquée";
            case 0x6984: return "Données invalides";
            case 0x6985: return "Conditions non remplies";
            case 0x6A80: return "Paramètres data incorrects";
            case 0x6A82: return "Fichier non trouvé";
            case 0x6A86: return "P1-P2 incorrects";
            case 0x6A88: return "Données référencées non trouvées";
            case 0x6D00: return "INS non supportée";
            case 0x6E00: return "CLA non supportée";
            case 0x6F00: return "Erreur inconnue";
            default:
                if ((sw & 0xFFF0) == 0x63C0) {
                    return "PIN incorrect, " + (sw & 0x0F) + " essais restants";
                }
                if ((sw & 0xFF00) == 0x6100) {
                    return (sw & 0x00FF) + " bytes disponibles (GET RESPONSE)";
                }
                return "Code inconnu";
        }
    }

    /**
     * Tente de décoder des bytes en ASCII lisible
     */
    private static String tryDecodeAscii(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            if (b >= 32 && b < 127) {
                sb.append((char) b);
            } else {
                sb.append('.');
            }
        }
        return sb.toString();
    }

    /**
     * Affiche l'aide du mode interactif
     */
    private static void printHelp() {
        System.out.println("\n┌─────────────────────────────────────────────┐");
        System.out.println("│              AIDE                            │");
        System.out.println("├─────────────────────────────────────────────┤");
        System.out.println("│ Commandes :                                  │");
        System.out.println("│   quit, exit, q  - Quitter                   │");
        System.out.println("│   help, ?        - Cette aide                │");
        System.out.println("│                                              │");
        System.out.println("│ Format APDU : CLA INS P1 P2 [Lc Data] [Le]  │");
        System.out.println("│                                              │");
        System.out.println("│ Exemples :                                   │");
        System.out.println("│   00A4040007A0000000010101  (SELECT)         │");
        System.out.println("│   0020000004 31323334       (VERIFY 1234)    │");
        System.out.println("│   00B0000010                (READ 16 bytes)  │");
        System.out.println("│   80100000                  (Custom INS)     │");
        System.out.println("└─────────────────────────────────────────────┘\n");
    }
}