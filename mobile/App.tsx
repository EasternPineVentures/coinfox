import React from 'react';
import {
  View,
  Text,
  ScrollView,
  SafeAreaView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  StatusBar,
} from 'react-native';
import {
  Bell,
  Heart,
  Home,
  MessageCircle,
  PlusSquare,
  Search,
  Settings,
  User,
} from 'lucide-react-native';

const palette = {
  bg: '#0b1020',
  panel: '#131a2e',
  panelAlt: '#1a2340',
  line: '#243152',
  text: '#f4f7fb',
  muted: '#92a0c6',
  accent: '#7c3aed',
  accent2: '#22c55e',
  danger: '#fb7185',
  warm: '#f59e0b',
};

type Story = {
  id: string;
  name: string;
  accent: string;
};

type Post = {
  id: string;
  author: string;
  handle: string;
  time: string;
  title: string;
  body: string;
  likes: number;
  comments: number;
  accent: string;
  tag: string;
};

const stories: Story[] = [
  { id: '1', name: 'Sora', accent: '#7c3aed' },
  { id: '2', name: 'Mina', accent: '#0ea5e9' },
  { id: '3', name: 'Theo', accent: '#f97316' },
  { id: '4', name: 'Jules', accent: '#22c55e' },
  { id: '5', name: 'Avery', accent: '#ec4899' },
];

const posts: Post[] = [
  {
    id: '1',
    author: 'Lena Hart',
    handle: '@lena',
    time: '12m ago',
    title: 'Launch day mood',
    body:
      'Just shipped the first version of our community app. Feed, profiles, comments, and a clean mobile layout are all in place.',
    likes: 128,
    comments: 18,
    accent: '#7c3aed',
    tag: 'Build',
  },
  {
    id: '2',
    author: 'Marco Vale',
    handle: '@marco',
    time: '48m ago',
    title: 'Coffee and creator tools',
    body:
      'Sketching out a new post composer with quick reactions, trending chips, and profile cards. This is such a fun design space.',
    likes: 84,
    comments: 9,
    accent: '#0ea5e9',
    tag: 'Design',
  },
  {
    id: '3',
    author: 'Nia Cole',
    handle: '@niac',
    time: '1h ago',
    title: 'Tiny wins count',
    body:
      'Friendly reminder that a simple, polished template can be more useful than an overbuilt MVP. Keep it shippable.',
    likes: 203,
    comments: 31,
    accent: '#22c55e',
    tag: 'Tips',
  },
];

function NavItem({
  icon,
  label,
  active = false,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <TouchableOpacity style={[styles.navItem, active && styles.navItemActive]}>
      {icon}
      <Text style={[styles.navLabel, active && styles.navLabelActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function StoryBubble({ story }: { story: Story }) {
  return (
    <View style={styles.storyWrap}>
      <View style={[styles.storyBubble, { borderColor: story.accent }]}>
        <View style={[styles.storyInner, { backgroundColor: story.accent }]} />
      </View>
      <Text style={styles.storyName}>{story.name}</Text>
    </View>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.statPill}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function PostCard({ post }: { post: Post }) {
  return (
    <View style={styles.postCard}>
      <View style={styles.postTop}>
        <View style={styles.postIdentityRow}>
          <View style={[styles.avatar, { backgroundColor: post.accent }]}>
            <Text style={styles.avatarText}>{post.author.charAt(0)}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.postAuthor}>{post.author}</Text>
            <Text style={styles.postMeta}>
              {post.handle} · {post.time}
            </Text>
          </View>
        </View>
        <View style={[styles.tagChip, { backgroundColor: post.accent + '22' }]}>
          <Text style={[styles.tagChipText, { color: post.accent }]}>{post.tag}</Text>
        </View>
      </View>

      <Text style={styles.postTitle}>{post.title}</Text>
      <Text style={styles.postBody}>{post.body}</Text>

      <View style={[styles.mediaCard, { borderColor: post.accent + '66' }]}>
        <View style={[styles.mediaGlow, { backgroundColor: post.accent + '33' }]} />
        <Text style={styles.mediaTitle}>Preview panel</Text>
        <Text style={styles.mediaText}>
          Drop an image, chart, or featured link here for a richer social post layout.
        </Text>
      </View>

      <View style={styles.postActions}>
        <View style={styles.actionItem}>
          <Heart size={16} color={palette.danger} />
          <Text style={styles.actionText}>{post.likes}</Text>
        </View>
        <View style={styles.actionItem}>
          <MessageCircle size={16} color={palette.muted} />
          <Text style={styles.actionText}>{post.comments}</Text>
        </View>
        <TouchableOpacity style={styles.followButton}>
          <Text style={styles.followButtonText}>Follow</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" />
      <View style={styles.appShell}>
        <View style={styles.topBar}>
          <View>
            <Text style={styles.brand}>CoinFox Social</Text>
            <Text style={styles.brandSub}>A simple community template for creators and conversations.</Text>
          </View>
          <View style={styles.topIcons}>
            <TouchableOpacity style={styles.iconButton}>
              <Search size={18} color={palette.text} />
            </TouchableOpacity>
            <TouchableOpacity style={styles.iconButton}>
              <Bell size={18} color={palette.text} />
            </TouchableOpacity>
          </View>
        </View>

        <ScrollView contentContainerStyle={styles.contentContainer} showsVerticalScrollIndicator={false}>
          <View style={styles.heroCard}>
            <View style={styles.heroCopy}>
              <Text style={styles.heroEyebrow}>Community template</Text>
              <Text style={styles.heroTitle}>Start with a polished social layout.</Text>
              <Text style={styles.heroText}>
                This starter includes a feed, profile summary, stories, compose box, and engagement UI using mock data.
              </Text>
              <View style={styles.heroStatsRow}>
                <StatPill label="Members" value="12.4k" />
                <StatPill label="Posts today" value="184" />
                <StatPill label="Engagement" value="94%" />
              </View>
            </View>
            <View style={styles.heroPanel}>
              <Text style={styles.panelTitle}>Your profile</Text>
              <View style={styles.profileCard}>
                <View style={[styles.avatarLarge, { backgroundColor: palette.accent }]}>
                  <Text style={styles.avatarLargeText}>C</Text>
                </View>
                <Text style={styles.profileName}>CoinFox Studio</Text>
                <Text style={styles.profileHandle}>@coinfox</Text>
                <Text style={styles.profileBio}>
                  Sharing market notes, product updates, and creator-focused community moments.
                </Text>
                <View style={styles.profileMetrics}>
                  <View>
                    <Text style={styles.metricValue}>8.2k</Text>
                    <Text style={styles.metricLabel}>Followers</Text>
                  </View>
                  <View>
                    <Text style={styles.metricValue}>312</Text>
                    <Text style={styles.metricLabel}>Following</Text>
                  </View>
                  <View>
                    <Text style={styles.metricValue}>57</Text>
                    <Text style={styles.metricLabel}>Posts</Text>
                  </View>
                </View>
              </View>
            </View>
          </View>

          <View style={styles.storiesRow}>
            <Text style={styles.sectionTitle}>Stories</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.storyScroll}>
              {stories.map((story) => (
                <StoryBubble key={story.id} story={story} />
              ))}
            </ScrollView>
          </View>

          <View style={styles.composerCard}>
            <Text style={styles.sectionTitle}>Create a post</Text>
            <TextInput
              placeholder="What do you want to share today?"
              placeholderTextColor={palette.muted}
              style={styles.composerInput}
              multiline
            />
            <View style={styles.composerFooter}>
              <View style={styles.composerChips}>
                <View style={styles.composerChip}><Text style={styles.composerChipText}>#launch</Text></View>
                <View style={styles.composerChip}><Text style={styles.composerChipText}>#design</Text></View>
                <View style={styles.composerChip}><Text style={styles.composerChipText}>#btc</Text></View>
              </View>
              <TouchableOpacity style={styles.publishButton}>
                <PlusSquare size={16} color={palette.text} />
                <Text style={styles.publishButtonText}>Publish</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.feedHeader}>
            <Text style={styles.sectionTitle}>Trending feed</Text>
            <TouchableOpacity>
              <Text style={styles.viewAll}>View all</Text>
            </TouchableOpacity>
          </View>

          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}

          <View style={styles.bottomPanel}>
            <View style={styles.bottomPanelCard}>
              <Text style={styles.panelTitle}>Suggested topics</Text>
              <View style={styles.topicWrap}>
                <Text style={styles.topicChip}>Product builds</Text>
                <Text style={styles.topicChip}>Creator economy</Text>
                <Text style={styles.topicChip}>Bitcoin</Text>
                <Text style={styles.topicChip}>UI inspiration</Text>
              </View>
            </View>
            <View style={styles.bottomPanelCard}>
              <Text style={styles.panelTitle}>Quick actions</Text>
              <Text style={styles.quickAction}>• Invite collaborators</Text>
              <Text style={styles.quickAction}>• Open profile editor</Text>
              <Text style={styles.quickAction}>• Add notifications panel</Text>
              <Text style={styles.quickAction}>• Connect a real backend later</Text>
            </View>
          </View>
        </ScrollView>

        <View style={styles.bottomNav}>
          <NavItem icon={<Home size={18} color={palette.text} />} label="Home" active />
          <NavItem icon={<MessageCircle size={18} color={palette.muted} />} label="Chat" />
          <NavItem icon={<PlusSquare size={18} color={palette.muted} />} label="Create" />
          <NavItem icon={<User size={18} color={palette.muted} />} label="Profile" />
          <NavItem icon={<Settings size={18} color={palette.muted} />} label="Settings" />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: palette.bg,
  },
  appShell: {
    flex: 1,
    backgroundColor: palette.bg,
  },
  topBar: {
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: palette.line,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  brand: {
    color: palette.text,
    fontSize: 24,
    fontWeight: '800',
  },
  brandSub: {
    color: palette.muted,
    marginTop: 4,
    maxWidth: 250,
    lineHeight: 18,
  },
  topIcons: {
    flexDirection: 'row',
    gap: 10,
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 14,
    backgroundColor: palette.panel,
    borderWidth: 1,
    borderColor: palette.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  contentContainer: {
    padding: 20,
    paddingBottom: 120,
    gap: 18,
  },
  heroCard: {
    gap: 16,
  },
  heroCopy: {
    backgroundColor: palette.panel,
    borderRadius: 24,
    padding: 20,
    borderWidth: 1,
    borderColor: palette.line,
  },
  heroEyebrow: {
    color: palette.accent2,
    fontWeight: '700',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 1,
    fontSize: 12,
  },
  heroTitle: {
    color: palette.text,
    fontSize: 28,
    lineHeight: 34,
    fontWeight: '800',
    marginBottom: 10,
  },
  heroText: {
    color: palette.muted,
    lineHeight: 21,
    fontSize: 15,
  },
  heroStatsRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 18,
    flexWrap: 'wrap',
  },
  statPill: {
    backgroundColor: palette.panelAlt,
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 12,
    minWidth: 92,
    borderWidth: 1,
    borderColor: palette.line,
  },
  statValue: {
    color: palette.text,
    fontSize: 16,
    fontWeight: '800',
  },
  statLabel: {
    color: palette.muted,
    marginTop: 3,
    fontSize: 12,
  },
  heroPanel: {
    backgroundColor: palette.panel,
    borderRadius: 24,
    padding: 20,
    borderWidth: 1,
    borderColor: palette.line,
  },
  panelTitle: {
    color: palette.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 14,
  },
  profileCard: {
    backgroundColor: palette.panelAlt,
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: palette.line,
    alignItems: 'center',
  },
  avatarLarge: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  avatarLargeText: {
    color: palette.text,
    fontSize: 28,
    fontWeight: '800',
  },
  profileName: {
    color: palette.text,
    fontSize: 20,
    fontWeight: '800',
  },
  profileHandle: {
    color: palette.muted,
    marginTop: 4,
  },
  profileBio: {
    color: palette.muted,
    textAlign: 'center',
    lineHeight: 20,
    marginTop: 12,
  },
  profileMetrics: {
    marginTop: 18,
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
  },
  metricValue: {
    color: palette.text,
    fontWeight: '800',
    fontSize: 18,
    textAlign: 'center',
  },
  metricLabel: {
    color: palette.muted,
    fontSize: 12,
    marginTop: 4,
    textAlign: 'center',
  },
  storiesRow: {
    backgroundColor: palette.panel,
    borderRadius: 24,
    padding: 20,
    borderWidth: 1,
    borderColor: palette.line,
  },
  storyScroll: {
    gap: 14,
    paddingRight: 8,
  },
  storyWrap: {
    alignItems: 'center',
    marginRight: 6,
  },
  storyBubble: {
    width: 68,
    height: 68,
    borderRadius: 34,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  storyInner: {
    width: 54,
    height: 54,
    borderRadius: 27,
  },
  storyName: {
    color: palette.text,
    fontSize: 12,
  },
  sectionTitle: {
    color: palette.text,
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 14,
  },
  composerCard: {
    backgroundColor: palette.panel,
    borderRadius: 24,
    padding: 20,
    borderWidth: 1,
    borderColor: palette.line,
  },
  composerInput: {
    minHeight: 110,
    backgroundColor: palette.panelAlt,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: palette.line,
    padding: 16,
    color: palette.text,
    textAlignVertical: 'top',
    marginBottom: 16,
  },
  composerFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    flexWrap: 'wrap',
  },
  composerChips: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  composerChip: {
    backgroundColor: palette.panelAlt,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.line,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  composerChipText: {
    color: palette.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  publishButton: {
    backgroundColor: palette.accent,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  publishButtonText: {
    color: palette.text,
    fontWeight: '700',
  },
  feedHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  viewAll: {
    color: palette.accent2,
    fontWeight: '700',
  },
  postCard: {
    backgroundColor: palette.panel,
    borderRadius: 24,
    padding: 18,
    borderWidth: 1,
    borderColor: palette.line,
    gap: 14,
  },
  postTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 10,
  },
  postIdentityRow: {
    flexDirection: 'row',
    gap: 12,
    flex: 1,
  },
  avatar: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    color: palette.text,
    fontSize: 18,
    fontWeight: '800',
  },
  postAuthor: {
    color: palette.text,
    fontSize: 16,
    fontWeight: '700',
  },
  postMeta: {
    color: palette.muted,
    marginTop: 3,
  },
  tagChip: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  tagChipText: {
    fontWeight: '700',
    fontSize: 12,
  },
  postTitle: {
    color: palette.text,
    fontSize: 20,
    fontWeight: '800',
  },
  postBody: {
    color: palette.muted,
    lineHeight: 21,
    fontSize: 14,
  },
  mediaCard: {
    backgroundColor: '#0f1630',
    borderRadius: 20,
    borderWidth: 1,
    padding: 16,
    overflow: 'hidden',
  },
  mediaGlow: {
    position: 'absolute',
    width: 180,
    height: 180,
    borderRadius: 90,
    top: -60,
    right: -20,
  },
  mediaTitle: {
    color: palette.text,
    fontWeight: '700',
    fontSize: 15,
    marginBottom: 6,
  },
  mediaText: {
    color: palette.muted,
    lineHeight: 20,
    maxWidth: '85%',
  },
  postActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  actionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  actionText: {
    color: palette.text,
    fontWeight: '700',
  },
  followButton: {
    backgroundColor: palette.panelAlt,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: palette.line,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  followButtonText: {
    color: palette.text,
    fontWeight: '700',
  },
  bottomPanel: {
    gap: 14,
  },
  bottomPanelCard: {
    backgroundColor: palette.panel,
    borderRadius: 24,
    padding: 20,
    borderWidth: 1,
    borderColor: palette.line,
  },
  topicWrap: {
    flexDirection: 'row',
    gap: 10,
    flexWrap: 'wrap',
  },
  topicChip: {
    color: palette.text,
    backgroundColor: palette.panelAlt,
    borderColor: palette.line,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    overflow: 'hidden',
  },
  quickAction: {
    color: palette.muted,
    lineHeight: 24,
  },
  bottomNav: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 16,
    backgroundColor: 'rgba(19, 26, 46, 0.96)',
    borderRadius: 22,
    borderWidth: 1,
    borderColor: palette.line,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    paddingVertical: 8,
  },
  navItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
    borderRadius: 16,
  },
  navItemActive: {
    backgroundColor: palette.panelAlt,
  },
  navLabel: {
    color: palette.muted,
    fontSize: 11,
    fontWeight: '700',
  },
  navLabelActive: {
    color: palette.text,
  },
});
