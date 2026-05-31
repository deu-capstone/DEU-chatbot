package com.deu.main_server.service;

import com.deu.main_server.dto.AiRequest;
import com.deu.main_server.dto.AiResponse;
import com.deu.main_server.dto.RecommendRequest;
import com.deu.main_server.dto.RecommendResponse;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.List;

@Service
public class AiService {

    private final RestClient restClient;

    public AiService() {
        this.restClient = RestClient.builder()
                .baseUrl("http://localhost:8000")
                .build();
    }

    public String askToFastApi(String question) {
        AiRequest requestDto = new AiRequest(question);

        AiResponse responseDto = this.restClient.post()
                .uri("/ask")
                .body(requestDto)
                .retrieve()
                .body(AiResponse.class);

        return responseDto != null ? responseDto.answer() : "AI 서버가 응답하지 않습니다.";
    }

    public RecommendResponse getRecommendationsFromFastApi(String department,   List<String> history) {
        RecommendRequest requestDto = new RecommendRequest(department, history);

        return this.restClient.post()
                .uri("/recommend")
                .body(requestDto)
                .retrieve()
                .body(RecommendResponse.class);
    }
}