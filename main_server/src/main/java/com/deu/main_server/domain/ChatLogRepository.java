package com.deu.main_server.domain;

import org.springframework.data.mongodb.repository.MongoRepository;
import java.util.List;

public interface ChatLogRepository extends MongoRepository<ChatLog, String> {
    List<ChatLog> findAllByEmailOrderByCreatedAtAsc(String email); // 과거 대화 순서대로 불러오기
    void deleteAllByEmail(String email); // 대화 기록 완전 삭제
}