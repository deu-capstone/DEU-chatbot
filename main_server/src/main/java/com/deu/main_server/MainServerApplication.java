package com.deu.main_server;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class MainServerApplication {

    public static void main(String[] args) {
        SpringApplication.run(MainServerApplication.class, args);
    }

}
// http://localhost:8080/test-ai?msg=메세지 입력
// http://127.0.0.1:8000/docs 주소창에 입력