export type FbUser = { name?: string };

export type FbComment = { from?: FbUser; message?: string };

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
