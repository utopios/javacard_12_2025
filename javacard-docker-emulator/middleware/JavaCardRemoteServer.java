/*
 * JavaCardRemoteServer.java - Serveur socket pour jCardSim
 * 
 * Ce serveur expose jCardSim via un socket TCP pour permettre
 * l'envoi de commandes APDU à distance.
 * 
 * Protocole:
 * - Client envoie: 2 bytes (big-endian) longueur + APDU
 * - Serveur répond: 2 bytes (big-endian) longueur + Response
 */
package com.licel.jcardsim.remote;

import com.licel.jcardsim.smartcardio.CardSimulator;
import com.licel.jcardsim.smartcardio.CardTerminalSimulator;

import javax.smartcardio.*;
import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.util.Properties;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class JavaCardRemoteServer {
    
    private final int port;
    private final CardSimulator simulator;
    private ServerSocket serverSocket;
    private ExecutorService executor;
    private volatile boolean running;
    
    public JavaCardRemoteServer(int port, Properties config) throws Exception {
        this.port = port;
        this.simulator = new CardSimulator();
        this.executor = Executors.newCachedThreadPool();
        
        // Charger les applets depuis la configuration
        loadApplets(config);
    }
    
    private void loadApplets(Properties config) throws Exception {
        int index = 0;
        while (true) {
            String aidStr = config.getProperty("com.licel.jcardsim.card.applet." + index + ".AID");
            String className = config.getProperty("com.licel.jcardsim.card.applet." + index + ".Class");
            
            if (aidStr == null || className == null) {
                break;
            }
            
            try {
                byte[] aidBytes = hexToBytes(aidStr);
                Class<?> appletClass = Class.forName(className);
                
                // Installer l'applet
                simulator.installApplet(
                    new javax.smartcardio.ATR(aidBytes),
                    appletClass
                );
                
                System.out.println("Loaded applet: " + className + " (AID: " + aidStr + ")");
            } catch (Exception e) {
                System.err.println("Failed to load applet " + className + ": " + e.getMessage());
            }
            
            index++;
        }
    }
    
    public void start() throws IOException {
        serverSocket = new ServerSocket(port);
        running = true;
        
        System.out.println("jCardSim Server listening on port " + port);
        
        while (running) {
            try {
                Socket clientSocket = serverSocket.accept();
                System.out.println("Client connected: " + clientSocket.getRemoteSocketAddress());
                executor.submit(new ClientHandler(clientSocket));
            } catch (IOException e) {
                if (running) {
                    System.err.println("Accept error: " + e.getMessage());
                }
            }
        }
    }
    
    public void stop() {
        running = false;
        try {
            if (serverSocket != null) {
                serverSocket.close();
            }
        } catch (IOException e) {
            // Ignore
        }
        executor.shutdown();
    }
    
    private class ClientHandler implements Runnable {
        private final Socket socket;
        private final DataInputStream in;
        private final DataOutputStream out;
        
        public ClientHandler(Socket socket) throws IOException {
            this.socket = socket;
            this.in = new DataInputStream(socket.getInputStream());
            this.out = new DataOutputStream(socket.getOutputStream());
        }
        
        @Override
        public void run() {
            try {
                while (running && !socket.isClosed()) {
                    // Lire la longueur de l'APDU (2 bytes big-endian)
                    int length = in.readUnsignedShort();
                    
                    // Lire l'APDU
                    byte[] apduBytes = new byte[length];
                    in.readFully(apduBytes);
                    
                    // Traiter l'APDU
                    byte[] responseBytes = processAPDU(apduBytes);
                    
                    // Envoyer la réponse
                    out.writeShort(responseBytes.length);
                    out.write(responseBytes);
                    out.flush();
                }
            } catch (EOFException e) {
                // Client déconnecté normalement
            } catch (IOException e) {
                System.err.println("Client error: " + e.getMessage());
            } finally {
                try {
                    socket.close();
                } catch (IOException e) {
                    // Ignore
                }
                System.out.println("Client disconnected");
            }
        }
        
        private byte[] processAPDU(byte[] apduBytes) {
            try {
                CommandAPDU command = new CommandAPDU(apduBytes);
                ResponseAPDU response = simulator.transmitCommand(command);
                return response.getBytes();
            } catch (Exception e) {
                System.err.println("APDU processing error: " + e.getMessage());
                // Retourner une erreur générique
                return new byte[] { 0x6F, 0x00 };
            }
        }
    }
    
    private static byte[] hexToBytes(String hex) {
        hex = hex.replaceAll("[^0-9A-Fa-f]", "");
        int len = hex.length();
        byte[] data = new byte[len / 2];
        for (int i = 0; i < len; i += 2) {
            data[i / 2] = (byte) ((Character.digit(hex.charAt(i), 16) << 4)
                                 + Character.digit(hex.charAt(i+1), 16));
        }
        return data;
    }
    
    public static void main(String[] args) {
        // Configuration par défaut
        int port = 9025;
        String configFile = null;
        
        // Parser les arguments
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("-p") || args[i].equals("--port")) {
                port = Integer.parseInt(args[++i]);
            } else if (!args[i].startsWith("-")) {
                configFile = args[i];
            }
        }
        
        // Charger la configuration
        Properties config = new Properties();
        if (configFile != null) {
            try (FileInputStream fis = new FileInputStream(configFile)) {
                config.load(fis);
            } catch (IOException e) {
                System.err.println("Failed to load config: " + e.getMessage());
            }
        }
        
        // Surcharger avec les variables d'environnement
        String envPort = System.getenv("JCARDSIM_PORT");
        if (envPort != null) {
            port = Integer.parseInt(envPort);
        }
        
        try {
            JavaCardRemoteServer server = new JavaCardRemoteServer(port, config);
            
            // Gérer l'arrêt propre
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                System.out.println("Shutting down...");
                server.stop();
            }));
            
            server.start();
        } catch (Exception e) {
            System.err.println("Server error: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
}
