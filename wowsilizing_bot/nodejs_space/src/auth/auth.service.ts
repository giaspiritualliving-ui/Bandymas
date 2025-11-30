import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { UserTier } from '../types/user-tier.enum';
import { Context } from 'telegraf';

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);
  private readonly premiumUsername: string;

  constructor(private configService: ConfigService) {
    this.premiumUsername = this.configService
      .get<string>('bot.premiumUsername')
      .toLowerCase()
      .replace('@', '');
    this.logger.log(`Premium username configured: ${this.premiumUsername}`);
  }

  /**
   * Determines if a user is premium based on their Telegram username
   */
  getUserTier(ctx: Context): UserTier {
    const username = ctx.from?.username?.toLowerCase();
    
    if (!username) {
      this.logger.warn(`User ${ctx.from?.id} has no username`);
      return UserTier.FREE;
    }

    const isPremium = username === this.premiumUsername;
    
    this.logger.debug(
      `User @${username} tier check: ${isPremium ? 'PREMIUM' : 'FREE'}`,
    );

    return isPremium ? UserTier.PREMIUM : UserTier.FREE;
  }

  /**
   * Checks if user has premium access
   */
  isPremiumUser(ctx: Context): boolean {
    return this.getUserTier(ctx) === UserTier.PREMIUM;
  }

  /**
   * Gets a user-friendly name from context
   */
  getUserName(ctx: Context): string {
    return (
      ctx.from?.username ||
      ctx.from?.first_name ||
      ctx.from?.id?.toString() ||
      'Unknown'
    );
  }
}
