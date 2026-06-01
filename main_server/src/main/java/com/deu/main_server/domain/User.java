package com.deu.main_server.domain;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import java.time.LocalDateTime;

@Document(collection = "users")
public class User {
    @Id
    private String id;
    private String email;
    private String username;
    private String fullName;
    private LocalDateTime joinedAt = LocalDateTime.now();

    // Getter, Setter, 생성자 (Lombok이 있다면 @Data로 대체 가능)
    public User() {}
    public User(String email, String username, String fullName) {
        this.email = email;
        this.username = username;
        this.fullName = fullName;
    }
    public String getEmail() { return email; }
    public String getFullName() { return fullName; }
    public void setFullName(String fullName) { this.fullName = fullName; }
}