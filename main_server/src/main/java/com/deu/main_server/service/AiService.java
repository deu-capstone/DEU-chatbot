package com.deu.main_server.service;

import com.deu.main_server.dto.AiRequest;
import com.deu.main_server.dto.AiResponse;
import com.deu.main_server.dto.RecommendRequest;
import com.deu.main_server.dto.RecommendResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.List;

@Service
public class AiService {

    private final RestClient restClient;

    public AiService() {
        // 1. 타임아웃을 설정할 수 있는 팩토리(Factory) 생성
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10000); // 연결 시도 시간 (10초)
        factory.setReadTimeout(60000);    // 🌟 AI 서버의 답변을 기다리는 시간 (60초로 넉넉하게 연장)

        // 2. 팩토리를 적용하여 RestClient 빌드
        this.restClient = RestClient.builder()
                .baseUrl("http://localhost:8000")
                .requestFactory(factory) // 생성한 설정 적용
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

    public RecommendResponse getRecommendationsFromFastApi(String department, List<String> history) {
        RecommendRequest requestDto = new RecommendRequest(department, history);

        return this.restClient.post()
                .uri("/recommend")
                .body(requestDto)
                .retrieve()
                .body(RecommendResponse.class);
    }
}