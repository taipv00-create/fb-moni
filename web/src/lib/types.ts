export type FbUser = { name?: string };

export type FbComment = {
  id?: string;
  from?: FbUser;
  message?: string;
  created_time?: string;
  attachment?: { type?: string };
  comments?: { data?: FbComment[]; summary?: { total_count?: number } };
};

export type FbAttachment = {
  type?: string;
  media?: { image?: { src?: string }; source?: string };
  url?: string;
};

export type FbPost = {
  id: string;
  message?: string;
  from?: FbUser;
  created_time?: string;
  permalink_url?: string;
  is_hidden?: boolean;
  _group_id?: string;
  reactions?: { summary?: { total_count?: number } };
  shares?: { count?: number };
  comments?: { data?: FbComment[]; summary?: { total_count?: number } };
  attachments?: { data?: FbAttachment[] };
};

export type FbPage = { id: string; name: string };

export type GroupRow = { id: string; name: string };

export type StaffAccount = {
  id?: string;
  name?: string;
  username?: string;
  role?: 'admin' | 'staff' | string;
  cookie_masked?: string;
  facebook_user_id?: string;
  enabled?: boolean;
};

export type BusinessProfile = {
  business_name?: string;
  phone?: string;
  address?: string;
  why_choose_us?: string;
  extra_notes?: string;
};

export type Lead = {
  name?: string;
  phone?: string;
  need?: string;
  source?: string;
  product_or_service?: string;
  location?: string;
  budget?: string;
  confidence?: number;
  evidence?: string;
};

export type ReplySuggestion = {
  post_id?: string;
  intent_label?: string;
  confidence?: number;
  target_source?: string;
  customer_name?: string;
  customer_need?: string;
  recommended_approach?: string;
  business_phone?: string;
  suggested_replies?: { label?: string; text?: string }[];
  storage?: string;
  warning?: string;
};

export type CommentSummary = {
  post_id?: string;
  comment_count?: number;
  fetched_comment_count?: number;
  comment_authors_count?: number;
  summary?: string;
  sentiment?: string;
  urgency?: string;
  main_topics?: string[];
  customer_intents?: { intent?: string; count?: number; evidence?: string }[];
  top_questions?: string[];
  notable_comments?: { author?: string; text?: string; reason?: string }[];
  lead_signals?: { author?: string; need?: string; evidence?: string }[];
  recommended_action?: string;
  spam_or_noise_count?: number;
  storage?: string;
  warning?: string;
};
