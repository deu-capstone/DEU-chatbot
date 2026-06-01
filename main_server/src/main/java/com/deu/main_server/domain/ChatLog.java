package com.deu.main_server.domain;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import java.time.LocalDateTime;

@Document(collection = "chats")
public class ChatLog {
    @Id
    private String id;
    private String email;
    private String sender; // "user" or "bot"
    private String text;
    private String timestamp;
    private LocalDateTime createdAt = LocalDateTime.now();

    public ChatLog() {}
    public ChatLog(String email, String sender, String text, String timestamp) {
        this.email = email;
        this.sender = sender;
        this.text = text;
        this.timestamp = timestamp;
    }

    // Getter, Setter
    public String getId() { return id; }
    public String getSender() { return sender; }
    public String getText() { return text; }
    public String getTimestamp() { return timestamp; }
}