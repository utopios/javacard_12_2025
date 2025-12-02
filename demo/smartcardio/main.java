import javax.smartcardio.*;
import java.util.List;

public class Main {
    public static void main(String[] args) {
        try {
            // Obtain the list of available terminals
            TerminalFactory factory = TerminalFactory.getDefault();
            List<CardTerminal> terminals = factory.terminals().list(CardTerminals.State.CARD_PRESENT));

            if (terminals.isEmpty()) {
                System.out.println("No card terminals found.");
                return;
            }

            CardTerminal card = null;
            
            for(CardTerminal terminal : terminals) {
                System.out.println("Found terminal: " + terminal.getName());
                card = terminal.connect("*");
                sout.println("Protcole: " + card.getProtocol());
                ATR atr = card.getATR();
                System.out.println("Card ATR: " + bytesToHex(atr.getBytes()));
                break;
            }
            if(card == null) {
                System.out.println("No card present in any terminal.");
                return;
            }
            
            //Create a channel to communicate with the card
            CardChannel channel = card.getBasicChannel();

            // select APPLET hello world with AID F0000000010001
            byte[] selectApplet = new byte[] {
                (byte)0x00, (byte)0xA4, (byte)0x04, (byte)0x00, (byte)0x07,
                (byte)0xF0, (byte)0x00, (byte)0x00, (byte)0x01, (byte)0x00, (byte)0x01
            };
            CommandAPDU selectCommand = new CommandAPDU(selectApplet);
            ResponseAPDU selectResponse = channel.transmit(selectCommand);

            System.out.println("Select Applet Response: " + bytesToHex(selectResponse.getBytes()));
            // Check if the applet was selected successfully
            if (selectResponse.getSW() != 0x9000) {
                System.out.println("Failed to select applet.");
            } else {
                System.out.println("Applet selected successfully.");
            }

            // Disconnect from the card
            card.disconnect(false);
            System.out.println("Card disconnected.");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // Helper method to convert byte array to hex string
    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02X ", b));
        }
        return sb.toString().trim();
    }
}