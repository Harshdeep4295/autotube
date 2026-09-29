import React from "react";
import {
  Bot, TriangleAlert, Battery, BookOpen, Brain, ChartColumn, MessageSquare, Check, Clock, Cloud,
  Code, Cpu, Database, DollarSign, Download, File, Settings, Globe, CircuitBoard, Image, Key,
  Laptop, Lightbulb, Lock, MemoryStick, Mic, WifiOff, Smartphone, Rocket, Search, Server, Shield,
  Star, SquareTerminal, TrendingDown, TrendingUp, Upload, User, Users, Video, X, Zap, LucideIcon,
} from "lucide-react";

// Keys must match ICONS in agents/scene_schema.py.
const MAP: Record<string, LucideIcon> = {
  ai: Bot, alert: TriangleAlert, battery: Battery, book: BookOpen, brain: Brain, chart: ChartColumn,
  chat: MessageSquare, check: Check, clock: Clock, cloud: Cloud, code: Code, cpu: Cpu,
  database: Database, dollar: DollarSign, download: Download, file: File, gear: Settings,
  globe: Globe, gpu: CircuitBoard, image: Image, key: Key, laptop: Laptop, lightbulb: Lightbulb,
  lock: Lock, memory: MemoryStick, mic: Mic, offline: WifiOff, phone: Smartphone, rocket: Rocket,
  search: Search, server: Server, shield: Shield, star: Star, terminal: SquareTerminal,
  "trending-down": TrendingDown, "trending-up": TrendingUp, upload: Upload, user: User,
  users: Users, video: Video, x: X, zap: Zap,
};

export const Icon: React.FC<{ name: string; size: number; color: string; stroke?: number }> = ({
  name, size, color, stroke = 2,
}) => {
  const Cmp = MAP[name] ?? Lightbulb;
  return <Cmp size={size} color={color} strokeWidth={stroke} />;
};
