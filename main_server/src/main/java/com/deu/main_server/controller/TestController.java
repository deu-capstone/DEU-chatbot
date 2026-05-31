package com.deu.main_server.controller;

import com.deu.main_server.dto.RecommendResponse;
import com.deu.main_server.service.AiService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.deu.main_server.dto.RecommendRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import java.util.ArrayList;

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

    @GetMapping("/test-recommend")
    public String testRecommend(@RequestParam String dept) {
        // 검색 기록은 일단 빈 배열로 넘기고, 학과(dept)만 테스트합니다.
        RecommendResponse response = aiService.getRecommendationsFromFastApi(dept, new ArrayList<>());

        if (response == null || response.recommendations() == null || response.recommendations().isEmpty()) {
            return "추천 공지가 없습니다.";
        }

        // 받아온 추천 결과를 깔끔한 HTML 형태로 조립해서 화면에 보여줍니다.
        StringBuilder sb = new StringBuilder("<h3>🎓 '" + dept + "' 관련 추천 공지사항 TOP 5</h3><ul>");

        response.recommendations().forEach(item -> {
            sb.append("<li><a href='").append(item.link()).append("' target='_blank'>")
                    .append(item.title()).append("</a></li>");
        });

        sb.append("</ul>");

        return sb.toString();
    }

    @PostMapping("/api/recommend")
    public RecommendResponse getRecommendByHistory(@RequestBody RecommendRequest request) {
        // 프론트엔드에서 보낸 JSON(학과, 검색기록 리스트)을 그대로 파이썬 서버로 토스!
        return aiService.getRecommendationsFromFastApi(request.department(), request.history());
    }
}