package com.deu.main_server.controller;

import com.deu.main_server.service.AiService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class TestController {

    private final AiService aiService;

    public TestController(AiService aiService) {
        this.aiService = aiService;
    }

    // 인터넷 브라우저에서 주소창을 통해 질문을 던질 수 있게 만듭니다.
    @GetMapping("/test-ai")
    public String testAi(@RequestParam String msg) {
        // 1. 브라우저에서 받은 질문(msg)을 AiService로 넘김
        String answer = aiService.askToFastApi(msg);

        // 2. 파이썬에서 만들어진 답변을 최종적으로 화면에 출력
        return "🤖 동의대 챗봇의 답변: " + answer;
    }
}