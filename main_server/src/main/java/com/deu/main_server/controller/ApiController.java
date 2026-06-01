package com.deu.main_server.controller;

import com.deu.main_server.domain.ChatLog;
import com.deu.main_server.domain.ChatLogRepository;
import com.deu.main_server.domain.User;
import com.deu.main_server.domain.UserRepository;
import com.deu.main_server.service.AiService;
import com.deu.main_server.dto.RecommendResponse;
import org.springframework.web.bind.annotation.*;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class ApiController {

    private final UserRepository userRepository;
    private final ChatLogRepository chatLogRepository;
    private final AiService aiService; // 🌟 파이썬(FastAPI)과 통신하는 기존 서비스

    public ApiController(UserRepository userRepository, ChatLogRepository chatLogRepository, AiService aiService) {
        this.userRepository = userRepository;
        this.chatLogRepository = chatLogRepository;
        this.aiService = aiService;
    }

    // 1. 구글 연동 회원가입 및 로그인 처리 API
    @PostMapping("/auth/google")
    public Map<String, Object> googleLogin(@RequestBody Map<String, String> payload) {
        String email = payload.get("email");
        String fullName = payload.get("fullName");
        String username = payload.get("username");

        User user = userRepository.findByEmail(email);
        if (user == null) {
            user = new User(email, username, fullName);
            userRepository.save(user);
        } else if (!user.getFullName().equals(fullName)) {
            user.setFullName(fullName);
            userRepository.save(user);
        }

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("user", user);
        return response;
    }

    // 2. 챗봇 대화 발송 및 MongoDB 대화 저장 API
    @PostMapping("/chat")
    public Map<String, Object> handleChat(@RequestBody Map<String, String> payload) {
        String email = payload.get("email");
        String message = payload.get("message");
        String timestamp = LocalTime.now().format(DateTimeFormatter.ofPattern("a hh:mm"));

        // 1) 사용자 메세지 DB 저장
        ChatLog userLog = new ChatLog(email, "user", message, timestamp);
        chatLogRepository.save(userLog);

        // 2) 🌟 파이썬 RAG 챗봇에게 답변 받아오기 (기존 하드코딩 대체!)
        String answer = aiService.askToFastApi(message);

        // 3) 챗봇 메세지 DB 저장
        String botTimestamp = LocalTime.now().format(DateTimeFormatter.ofPattern("a hh:mm"));
        ChatLog botLog = new ChatLog(email, "bot", answer, botTimestamp);
        chatLogRepository.save(botLog);

        // 4) 프론트엔드로 응답 반환
        Map<String, Object> response = new HashMap<>();
        response.put("id", botLog.getId());
        response.put("sender", "bot");
        response.put("text", answer);
        response.put("timestamp", botTimestamp);
        return response;
    }

    // 3. 채팅 기록 불러오기 API
    @GetMapping("/chat/history")
    public List<ChatLog> getChatHistory(@RequestParam String email) {
        return chatLogRepository.findAllByEmailOrderByCreatedAtAsc(email);
    }

    // 4. 채팅 기록 완전 삭제 API
    @DeleteMapping("/chat/history")
    public Map<String, Object> deleteChatHistory(@RequestParam String email) {
        chatLogRepository.deleteAllByEmail(email);

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("message", "서버 데이터베이스 내 상담 로그가 전건 삭제되었습니다.");
        return response;
    }

    @PostMapping("/recommend")
    public RecommendResponse getRecommendations(@RequestBody Map<String, Object> payload) {
        String department = (String) payload.getOrDefault("department", "");

        // 검색 기록(history) 캐스팅 안전하게 처리
        List<String> history;
        if (payload.get("history") instanceof List) {
            history = (List<String>) payload.get("history");
        } else {
            history = List.of();
        }

        // AiService가 반환하는 RecommendResponse를 그대로 프론트엔드로 전달!
        return aiService.getRecommendationsFromFastApi(department, history);
    }
}