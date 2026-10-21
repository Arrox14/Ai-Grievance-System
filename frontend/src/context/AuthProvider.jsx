import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import axios from "axios";
import { AuthContext } from "./AuthContext";

const API_BASE = "http://127.0.0.1:8000";
const TOKEN_KEY = "pgis_token";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [sessionError, setSessionError] = useState("");
  const tokenRef = useRef(token);
  const expiredRef = useRef(false);

  const clearSession = useCallback((expired = false) => {
    sessionStorage.removeItem(TOKEN_KEY);
    tokenRef.current = null;
    expiredRef.current = expired;
    setToken(null);
    setUser(null);
    setSessionError("");
  }, []);

  const verifySession = useCallback(async (candidateToken = tokenRef.current) => {
    if (!candidateToken) {
      clearSession();
      setReady(true);
      return null;
    }

    setSessionError("");
    try {
      const response = await axios.get(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${candidateToken}` },
      });
      tokenRef.current = candidateToken;
      sessionStorage.setItem(TOKEN_KEY, candidateToken);
      setToken(candidateToken);
      setUser(response.data);
      expiredRef.current = false;
      return response.data;
    } catch (error) {
      if (error.response?.status === 401) {
        clearSession(true);
        return null;
      }

      setSessionError("Unable to verify your session. Check your connection and retry.");
      return null;
    } finally {
      setReady(true);
    }
  }, [clearSession]);

  useEffect(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem("pgis_user");

    const requestInterceptor = axios.interceptors.request.use((config) => {
      if (config.url?.startsWith(API_BASE)) {
        if (tokenRef.current) {
          config.headers.Authorization = `Bearer ${tokenRef.current}`;
        } else if (!config.url.endsWith("/logout")) {
          delete config.headers.Authorization;
        }
      }
      return config;
    });

    const responseInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (
          error.response?.status === 401 &&
          tokenRef.current &&
          !error.config?.url?.endsWith("/login") &&
          !error.config?.url?.endsWith("/register")
        ) {
          clearSession(true);
        }
        return Promise.reject(error);
      }
    );

    verifySession();
    return () => {
      axios.interceptors.request.eject(requestInterceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
  }, [clearSession, verifySession]);

  const establishSession = useCallback(async (nextToken) => {
    tokenRef.current = nextToken;
    sessionStorage.setItem(TOKEN_KEY, nextToken);
    setToken(nextToken);
    expiredRef.current = false;
    setSessionError("");
    return verifySession(nextToken);
  }, [verifySession]);

  const login = useCallback(async (email, password, expectedRole) => {
    const response = await axios.post(`${API_BASE}/login`, { email, password });
    if (expectedRole && response.data.user?.role !== expectedRole) {
      throw new Error(
        `This account is not authorized for ${expectedRole} login.`
      );
    }
    const authenticatedUser = await establishSession(response.data.access_token);
    if (!authenticatedUser) {
      throw new Error("Login succeeded, but the session could not be verified.");
    }
    return authenticatedUser;
  }, [establishSession]);

  const register = useCallback(async (name, email, password) => {
    const response = await axios.post(`${API_BASE}/register`, {
      name,
      email,
      password,
    });
    const authenticatedUser = await establishSession(response.data.access_token);
    if (!authenticatedUser) {
      throw new Error("Registration succeeded, but the session could not be verified.");
    }
    return authenticatedUser;
  }, [establishSession]);

  const logout = useCallback(async () => {
    const currentToken = tokenRef.current;
    clearSession();
    if (!currentToken) return;

    try {
      await axios.post(
        `${API_BASE}/logout`,
        {},
        { headers: { Authorization: `Bearer ${currentToken}` } }
      );
    } catch (error) {
      if (error.response?.status !== 401) {
        console.error("Unable to invalidate the server session:", error);
      }
    }
  }, [clearSession]);

  const retrySession = useCallback(() => {
    setReady(false);
    return verifySession();
  }, [verifySession]);

  const value = useMemo(
    () => ({
      token,
      user,
      ready,
      sessionError,
      sessionExpired: expiredRef.current,
      isAuthenticated: Boolean(token && user),
      isCitizen: user?.role === "citizen",
      isAdmin: user?.role === "admin",
      isOfficer: user?.role === "officer",
      login,
      register,
      logout,
      retrySession,
    }),
    [token, user, ready, sessionError, login, register, logout, retrySession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
