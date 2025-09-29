import logging
from rich.logging import RichHandler
import os
import sys
import json

sys.path.extend(['.', '..'])

_config_file = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')), 'main_config.json')

with open(_config_file, 'r', encoding='utf-8') as f:
    CONFIG = json.loads(f.read())['coverage']

code_base = CONFIG['code_base']

def init_logger(project_name="myproject"):
    logger = logging.getLogger(project_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False   # 🚨 禁止把日志传给 root

    # 清理旧 handler，避免重复打印
    logger.handlers.clear()

    handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,   # 关掉时间
        show_path=True,   # 关掉路径
        show_level=True    # 只保留彩色等级 + message
    )

    # RichHandler 自己控制格式，这里只留 message
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


# 使用
logger = init_logger("current_file_logger")


# logger = logging.getLogger('current_file_logger')
# logger.setLevel(logging.DEBUG)  # 设置日志级别
# logger.propagate = False

# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('[%(asctime)s - %(filename)s - %(funcName)s] - %(message)s')
# console_handler.setFormatter(formatter)
# logger.addHandler(console_handler)
    
example_response = """
Here are the additional test cases for the `org.llm.NonGenericClass.createContainer` function:

```java
package org.llm;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class NonGenericClassTest {

    @Test
    public void testCreateContainerWithNullValue() {
        NonGenericClass nonGenericClass = new NonGenericClass();
        assertThrows(IllegalArgumentException.class, () -> nonGenericClass.createContainer(null));
    }

    @Test
    public void testCreateContainerWithLongValue() {
        NonGenericClass nonGenericClass = new NonGenericClass();
        String longString = "This is a string with more than ten characters.";
        GenericContainer<String> container = nonGenericClass.createContainer(longString);
        assertEquals("Too Long", container.getValue());
    }

    @Test
    public void testCreateContainerWithVariousValues() {
        NonGenericClass nonGenericClass = new NonGenericClass();
        GenericContainer<String> container1 = nonGenericClass.createContainer("Hello");
        assertEquals("Hello", container1.getValue());

        GenericContainer<String> container2 = nonGenericClass.createContainer("");
        assertEquals("Default Value", container2.getValue());

        String longString = "This is a string with more than ten characters.";
        GenericContainer<String> container3 = nonGenericClass.createContainer(longString);
        assertEquals("Too Long", container3.getValue());

        assertThrows(IllegalArgumentException.class, () -> nonGenericClass.createContainer(null));
    }
}
```

These test cases cover different scenarios such as null value, long string, and a combination of valid, empty, and null values.
"""

example_test = '''
package org.utbench.productline.mybatis.service;

import com.alibaba.fastjson.*;
import org.apache.commons.lang3.*;
import org.jetbrains.annotations.*;
import org.springframework.beans.factory.annotation.*;
import org.springframework.dao.*;
import org.springframework.stereotype.*;
import org.springframework.util.*;
import org.utbench.productline.model.*;
import org.utbench.productline.mybatis.dao.*;
import org.utbench.productline.mybatis.model.*;
import org.utbench.productline.mybatis.model.enums.*;
import org.utbench.productline.mybatis.util.*;
import org.utbench.productline.mybatis.vo.*;
import java.nio.charset.*;
import java.util.*;
import java.util.stream.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.*;
import org.mockito.junit.jupiter.*;
import java.util.*;
import org.mockito.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.AdditionalMatchers.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import static java.util.Optional.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.MockitoAnnotations.*;
import java.util.stream.*;
import org.junit.jupiter.api.io.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.*;
import org.mockito.junit.jupiter.*;
import java.util.*;
import org.mockito.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.AdditionalMatchers.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import static java.util.Optional.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.MockitoAnnotations.*;
import java.util.stream.*;
import org.junit.jupiter.api.io.*;
import org.mockito.quality.Strictness;
import org.springframework.test.util.ReflectionTestUtils;
import org.utbench.productline.mybatis.dao.*;
import okhttp3.*;
import org.utbench.productline.mybatis.util.*;
import org.utbench.productline.mybatis.service.*;
import java.time.*;
import org.utbench.productline.object.vo.*;
import org.utbench.productline.mybatis.model.enums.*;
import org.springframework.dao.*;
import org.utbench.productline.mybatis.model.*;
import org.apache.http.client.methods.*;
import org.utbench.productline.mybatis.vo.*;
import org.utbench.productline.model.*;
import com.baomidou.mybatisplus.extension.conditions.query.*;
import org.springframework.web.client.*;
import java.lang.reflect.*;

@MockitoSettings(strictness = Strictness.LENIENT)
public class UserServicelogin79508580378Test{
@Mock(answer = Answers.RETURNS_DEEP_STUBS)
private UserDao userDao;
@Mock(answer = Answers.RETURNS_DEEP_STUBS)
private VerifyCodeService verifyCodeService;
@InjectMocks
private UserService userService;
private AutoCloseable mockitoCloseable;
@BeforeEach
void setUp() throws Exception {
mockitoCloseable = MockitoAnnotations.openMocks(this);
ReflectionTestUtils.setField(userService, "DEFAULT_CODE", "string");
ReflectionTestUtils.setField(userService, "ADMIN_NAME", "string");
ReflectionTestUtils.setField(userService, "DEFAULT_OFFSET", 0);
ReflectionTestUtils.setField(userService, "DEFAULT_LIMIT", 0);
ReflectionTestUtils.setField(userService, "MAX_LIMIT", 0);
}
@AfterEach
void tearDown() throws Exception {
mockitoCloseable.close();
}


// successfully compiled! 
@Test
    void testLoginWithNonExistUser() {
        when(userDao.getUserByName(anyString())).thenReturn(null);
        ResResult<UserVO> result = userService.login("nonexistuser", "anypassword");
        assertEquals("用户名或密码错误!", result.getMsg());
    }

// successfully compiled! 
@Test
    void testLoginWithEmptyUserName() {
        ResResult<UserVO> result = userService.login("", "anypassword");
        assertEquals("用户名和密码不能为空!", result.getMsg());
    }

// successfully compiled! 
@Test
    void testLoginWithEmptyPassword() {
        ResResult<UserVO> result = userService.login("userName", "");
        assertEquals("用户名和密码不能为空!", result.getMsg());
    }

// successfully compiled! 
@Test
    void testLoginWithNullUserName() {
        ResResult<UserVO> result = userService.login(null, "password");
        assertEquals("用户名和密码不能为空!", result.getMsg());
    }

// successfully compiled! 
@Test
    void testLoginWithNullPassword() {
        ResResult<UserVO> result = userService.login("username", null);
        assertEquals("用户名和密码不能为空!", result.getMsg());
    }

// successfully compiled! 
@Test
    void testLoginWithBothNull() {
        ResResult<UserVO> result = userService.login(null, null);
        assertEquals("用户名和密码不能为空!", result.getMsg());
    }

// successfully compiled! 
@Test
    void testLoginWithBothEmpty() {
        ResResult<UserVO> result = userService.login("", "");
        assertEquals("用户名和密码不能为空!", result.getMsg());
    }

'''